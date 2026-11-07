"""The ONLY path from agents to shop data: our FastMCP server over stdio.

There is no second tools layer. Every agent sees a filtered view of the
same MCP server (an allowlist per role, in backend/agents/*.py), and every
call goes through `stamp_and_guard` first:

1. Identity is stamped by code, not trusted from the model: the
   requested_by / author / updated_by argument is overwritten with the
   calling agent's name, so an agent can't act as someone else.
2. Human-only tools (record_human_decision, execute_approved_payment) are
   blocked even if one somehow got into an allowlist.
3. Board rules: only customer_service writes draft_message, only boss
   writes decision.
Blocked calls return an error dict to the model and are written to the
audit trail as "guardrail" events.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastmcp.client.transports import StdioTransport
from pydantic_ai import RunContext
from pydantic_ai.mcp import MCPToolset

from . import audit
from .models import TeamDeps

ROOT = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = ROOT / "mcp_server" / "server.py"

HUMAN_ONLY_TOOLS = frozenset({"record_human_decision", "execute_approved_payment"})
IDENTITY_ARG = {
    "request_payment": "requested_by",
    "request_purchase_order": "requested_by",
    "post_to_board": "author",
    "update_ticket_status": "updated_by",
}


def _guard(deps: TeamDeps, name: str, args: dict[str, Any]) -> str | None:
    if name in HUMAN_ONLY_TOOLS:
        return f"{name} is human-only. Agents can request approvals but never approve or pay."
    if name == "post_to_board":
        kind = args.get("kind")
        if kind == "draft_message" and deps.agent != "customer_service":
            return "Only customer_service writes customer drafts. Delegate to customer_service."
        if kind == "decision" and deps.agent != "boss":
            return "Only boss posts decisions. Post a 'note' instead."
    return None


async def stamp_and_guard(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
    deps = ctx.deps
    if name in IDENTITY_ARG:
        args = {**args, IDENTITY_ARG[name]: deps.agent}
    blocked = _guard(deps, name, args)
    if blocked:
        audit.append({
            "ticket_run_id": deps.ticket_run_id, "ticket_id": deps.ticket_id,
            "agent": deps.agent, "agent_run_id": deps.agent_run_id, "chain": deps.chain,
            "event": "guardrail", "tool_calls": [{"tool": name, "args": audit.short(args)}],
            "text": blocked, "stop_reason": "blocked",
        })
        return {"ok": False, "blocked_by_guardrail": True, "message": blocked}
    return await call_tool(name, args)


def build_shop_toolset() -> MCPToolset:
    """One MCP connection (a child process running mcp_server/server.py)."""
    transport = StdioTransport(command=sys.executable, args=[str(SERVER_SCRIPT)], cwd=str(ROOT))
    return MCPToolset(transport, id="campus_customs", process_tool_call=stamp_and_guard,
                      tool_error_behavior="retry", max_retries=2)


def view_for(shop: MCPToolset, allowed: frozenset[str]):
    """A per-agent view of the shared MCP server, limited to its allowlist."""
    bad = allowed & HUMAN_ONLY_TOOLS
    if bad:
        raise ValueError(f"Human-only tools cannot be given to an agent: {sorted(bad)}")
    return shop.filtered(lambda ctx, tool_def: tool_def.name in allowed)
