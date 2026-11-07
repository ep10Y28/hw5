"""The Campus Customs agent team (PydanticAI) and its agent loop.

Five agents (backend/agents/*.py) share:
- one model: gpt-6-luna via Portkey (backend/llm.py), and nothing else
- one MCP server: mcp_server/server.py over stdio (backend/mcp_link.py);
  each agent sees only its allowlisted tools
- one delegate tool: full connectivity, any agent can ask any other agent

Agent loop: every run goes through `agent.iter()`, so each loop step
(model response -> tool calls -> tool results) is written to
output/audit_trail.json while it happens.

Budgets that keep tokens in check (all per ticket run, shared by every
agent that touches the ticket):
- TICKET_LIMITS: max model requests, tool calls and total tokens
- MAX_DEPTH: Boss -> A -> B at most (no deeper chains)
- TicketBudget.max_delegations: max hand-offs per ticket
- no cycles: an agent can't delegate back to someone already in the chain
- MODEL_SETTINGS.max_tokens: cap on each model reply
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage

from . import audit
from .agents import ROLES
from .llm import MODEL_NAME, build_model
from .mcp_link import build_shop_toolset, view_for
from .models import AgentName, TeamDeps, TicketBudget, TicketOutcome

MAX_DEPTH = 2
TICKET_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=60, total_tokens_limit=150_000)
MODEL_SETTINGS = ModelSettings(max_tokens=4000)


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _usage(u: RunUsage) -> dict:
    return {"requests": u.requests, "tool_calls": getattr(u, "tool_calls", None),
            "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}


def _base(deps: TeamDeps) -> dict:
    return {"ticket_run_id": deps.ticket_run_id, "ticket_id": deps.ticket_id,
            "agent": deps.agent, "agent_run_id": deps.agent_run_id,
            "parent_agent_run_id": deps.parent_agent_run_id,
            "chain": deps.chain, "depth": deps.depth, "model": MODEL_NAME}


class CampusTeam:
    """Builds the five agents once. Use `async with team:` to open the MCP connection."""

    def __init__(self, model: Model | None = None):
        self.model = model if model is not None else build_model()
        self.shop = build_shop_toolset()
        self.agents: dict[str, Agent] = {name: self._build(name) for name in ROLES}

    async def __aenter__(self):
        await self.shop.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self.shop.__aexit__(*exc)

    # ------------------------------------------------------------ building

    def _build(self, name: str) -> Agent:
        role = ROLES[name]
        prompt_text = role.PROMPT_FILE.read_text(encoding="utf-8")
        team_lines = "\n".join(f"- {n}: {r.ROLE}" for n, r in ROLES.items() if n != name)

        agent = Agent(
            self.model,
            name=name,
            deps_type=TeamDeps,
            output_type=role.OUTPUT,
            instructions=prompt_text,
            toolsets=[view_for(self.shop, role.MCP_TOOLS)],
            model_settings=MODEL_SETTINGS,
            retries=2,
        )

        @agent.instructions
        def run_context(ctx: RunContext[TeamDeps]) -> str:
            d = ctx.deps
            return (
                f"## This run\n"
                f"- You are: {d.agent}\n"
                f"- Ticket: {d.ticket_id if d.ticket_id is not None else 'none'}\n"
                f"- Delegation chain so far: {' -> '.join(d.chain)}\n"
                f"- Delegations left on this ticket: {d.budget.max_delegations - d.budget.delegations}; "
                f"max chain depth {MAX_DEPTH} (you are at depth {d.depth})\n"
                f"## Your teammates (use the delegate tool)\n{team_lines}\n"
            )

        team = self

        @agent.tool
        async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict[str, Any]:
            """Ask another agent to do part of the work and return its report.

            to_agent: boss | inventory | accounting | facilities | customer_service (not yourself).
            task: a specific, self-contained request with the ticket id, sku/size/qty,
                  invoice or lease ids, and the exact question or action you need.
            """
            return await team._delegate(ctx, to_agent, task)

        return agent

    # ------------------------------------------------------------ delegation

    async def _delegate(self, ctx: RunContext[TeamDeps], to_agent: str, task: str) -> dict[str, Any]:
        d = ctx.deps
        problem = None
        if to_agent == d.agent:
            problem = "You can't delegate to yourself."
        elif to_agent in d.chain:
            problem = (f"{to_agent} is already in this chain ({' -> '.join(d.chain)}). "
                       "Answer your caller with what you have instead of looping back.")
        elif d.depth + 1 > MAX_DEPTH:
            problem = f"Max delegation depth ({MAX_DEPTH}) reached. Finish with what you have."
        elif d.budget.delegations >= d.budget.max_delegations:
            problem = "No delegations left on this ticket. Finish with what you have."
        if problem:
            audit.append({**_base(d), "event": "guardrail", "stop_reason": "blocked",
                          "tool_calls": [{"tool": "delegate", "args": audit.short({"to_agent": to_agent, "task": task})}],
                          "text": problem})
            return {"ok": False, "message": problem}

        d.budget.delegations += 1
        child = TeamDeps(agent=to_agent, ticket_id=d.ticket_id, ticket_run_id=d.ticket_run_id,
                         agent_run_id=_new_id(), parent_agent_run_id=d.agent_run_id,
                         chain=[*d.chain, to_agent], budget=d.budget)
        audit.append({**_base(d), "event": "delegation", "text": audit.short(task),
                      "tool_calls": [{"tool": "delegate", "args": audit.short({"to_agent": to_agent})}],
                      "delegated_to": to_agent, "child_agent_run_id": child.agent_run_id})
        try:
            report = await self.run_agent(to_agent, task, child, usage=ctx.usage)
        except UsageLimitExceeded:
            raise  # the whole ticket is over budget: stop everything
        except Exception as exc:  # child failed: tell the caller, don't crash the ticket
            return {"ok": False, "agent": to_agent, "error": audit.short(str(exc), 300)}
        return {"ok": True, **report.model_dump()}

    # ------------------------------------------------------------ the agent loop

    async def run_agent(self, name: str, prompt: str, deps: TeamDeps, usage: RunUsage):
        """Run one agent through its loop, auditing every step as it happens."""
        agent = self.agents[name]
        started = time.monotonic()
        audit.append({**_base(deps), "event": "run_start", "text": audit.short(prompt)})
        step = 0
        names_by_call: dict[str, str] = {}
        try:
            async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=TICKET_LIMITS) as run:
                async for node in run:
                    if Agent.is_call_tools_node(node):
                        step += 1
                        resp: ModelResponse = node.model_response
                        calls = [p for p in resp.parts if isinstance(p, ToolCallPart)]
                        for c in calls:
                            names_by_call[c.tool_call_id] = c.tool_name
                        text = " ".join(p.content for p in resp.parts if isinstance(p, TextPart)).strip()
                        out_call = any(c.tool_name.startswith("final_result") for c in calls)
                        audit.append({
                            **_base(deps), "event": "model_step", "step": step,
                            "text": audit.short(text) if text else None,
                            "tool_calls": [{"tool": c.tool_name, "args": audit.short(c.args_as_dict())} for c in calls],
                            "tokens": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
                            "ticket_usage": _usage(run.usage),
                            "stop_reason": "final_result" if out_call or not calls else "tool_call",
                        })
                    elif Agent.is_model_request_node(node) and step > 0:
                        results = []
                        for p in node.request.parts:
                            if isinstance(p, ToolReturnPart):
                                results.append({"tool": p.tool_name, "result": audit.short(p.content)})
                            elif isinstance(p, RetryPromptPart):
                                results.append({"tool": p.tool_name or names_by_call.get(p.tool_call_id, "?"),
                                                "retry": audit.short(p.content)})
                        if results:
                            audit.append({**_base(deps), "event": "tool_results", "step": step,
                                          "tool_results": results,
                                          "stop_reason": "retry" if any("retry" in r for r in results) else "tool_call"})
                result = run.result
        except UsageLimitExceeded as exc:
            audit.append({**_base(deps), "event": "error", "step": step, "stop_reason": "usage_limit",
                          "text": audit.short(str(exc)), "ticket_usage": _usage(usage)})
            raise
        except Exception as exc:
            audit.append({**_base(deps), "event": "error", "step": step, "stop_reason": "error",
                          "text": audit.short(f"{type(exc).__name__}: {exc}"), "ticket_usage": _usage(usage)})
            raise
        audit.append({**_base(deps), "event": "run_end", "step": step, "stop_reason": "final_result",
                      "text": audit.short(result.output), "output": result.output.model_dump(),
                      "ticket_usage": _usage(usage),
                      "duration_ms": int((time.monotonic() - started) * 1000)})
        return result.output

    # ------------------------------------------------------------ entry points

    async def run_ticket(self, ticket_id: int, ticket_run_id: str | None = None) -> TicketOutcome:
        """Boss works one ticket end to end (delegating as needed)."""
        deps = TeamDeps(agent="boss", ticket_id=ticket_id, ticket_run_id=ticket_run_id or _new_id(),
                        agent_run_id=_new_id(), chain=["boss"], budget=TicketBudget())
        prompt = (f"Work ticket {ticket_id}. Start with get_ticket({ticket_id}), route the work to the "
                  f"right teammates, and finish with your final call as a TicketOutcome.")
        outcome = await self.run_agent("boss", prompt, deps, usage=RunUsage())
        await self._close_ticket(deps, outcome)
        return outcome

    async def _close_ticket(self, deps: TeamDeps, outcome: TicketOutcome) -> None:
        """When Boss's run finishes, the team's work on the ticket is done, so the
        ticket is marked resolved (on Boss's behalf) if Boss didn't already do it.
        Anything still waiting on a person stays visible: pending approvals in
        the approvals table and the needs_human list in the decision note."""
        current = await self.shop.direct_call_tool("get_ticket", {"ticket_id": deps.ticket_id})
        if current.get("ticket", {}).get("status") == "resolved":
            return
        waiting = "; ".join(outcome.needs_human) or "nothing"
        note = f"Agent run {deps.ticket_run_id} finished. Boss: {outcome.decision} Waiting on a human: {waiting}"
        res = await self.shop.direct_call_tool("update_ticket_status", {
            "ticket_id": deps.ticket_id, "status": "resolved", "note": note[:1500], "updated_by": "boss"})
        audit.append({**_base(deps), "event": "ticket_closed", "stop_reason": "resolved",
                      "text": audit.short(note), "tool_results": [{"tool": "update_ticket_status",
                                                                    "result": audit.short(res)}]})

    async def ask(self, agent_name: str, question: str, ticket_id: int | None = None):
        """Ask any single agent directly (useful for testing one role)."""
        deps = TeamDeps(agent=agent_name, ticket_id=ticket_id, ticket_run_id=_new_id(),
                        agent_run_id=_new_id(), chain=[agent_name], budget=TicketBudget())
        return await self.run_agent(agent_name, question, deps, usage=RunUsage())
