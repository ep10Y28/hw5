"""Data types shared by the Campus Customs agent team.

- TeamDeps ........ what every agent run carries (who it is, which ticket,
                    who delegated to it, shared counters for budgets).
- AgentReport ..... structured result every specialist returns.
- TicketOutcome ... Boss's final structured call on a ticket.
- AgentName / TicketStatus / BoardKind ... the allowed values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[str, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

TicketStatus = Literal["open", "in_progress", "waiting_approval", "blocked", "resolved"]
BoardKind = Literal["draft_message", "note", "decision"]


@dataclass
class TicketBudget:
    """Counters shared by every agent working one ticket (token/cost control)."""
    delegations: int = 0
    max_delegations: int = 8


@dataclass
class TeamDeps:
    """Passed to every agent run. Child runs get a copy with a longer chain."""
    agent: str                      # which agent this run is
    ticket_id: int | None           # ticket being worked (None = general question)
    ticket_run_id: str              # ties every audit entry for one ticket run together
    agent_run_id: str               # this agent's run
    parent_agent_run_id: str | None = None
    chain: list[str] = field(default_factory=list)  # e.g. ["boss", "accounting"]
    budget: TicketBudget = field(default_factory=TicketBudget)

    @property
    def depth(self) -> int:
        return len(self.chain) - 1


class AgentReport(BaseModel):
    """What a specialist (Inventory, Accounting, Facilities, Customer Service)
    hands back to whoever asked it. Every number must come from a tool result."""
    agent: AgentName
    summary: str = Field(description="2-4 sentences: what you found and did.")
    facts: list[str] = Field(default_factory=list,
                             description="Facts from MCP tool results, each with its number and source table.")
    actions_taken: list[str] = Field(default_factory=list,
                                     description="Writes you made (approval queued, board post, status change).")
    approval_ids: list[int] = Field(default_factory=list,
                                    description="Approval ids returned by request_payment / request_purchase_order.")
    board_ids: list[int] = Field(default_factory=list, description="Board ids returned by post_to_board.")
    blockers: list[str] = Field(default_factory=list,
                                description="What stops this ticket (open invoice, cash, stock, human approval).")
    recommendation: str = Field(default="", description="What you advise Boss to do next.")


class TicketOutcome(BaseModel):
    """Boss's final call on one ticket."""
    ticket_id: int
    decision: str = Field(description="Boss's final call in 1-3 sentences.")
    agents_consulted: list[AgentName] = Field(default_factory=list)
    actions_taken: list[str] = Field(default_factory=list)
    approval_ids: list[int] = Field(default_factory=list,
                                    description="Requests now waiting for a human on the dashboard.")
    board_ids: list[int] = Field(default_factory=list)
    final_status: TicketStatus = Field(description="'resolved' when the team's part is done (pending human items go in needs_human).")
    needs_human: list[str] = Field(default_factory=list,
                                   description="Exactly what a person must approve, send, or decide.")
