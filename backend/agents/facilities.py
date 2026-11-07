"""Facilities: the shop space - leases, rent, landlord."""
from pathlib import Path
from ..models import AgentReport

NAME = "facilities"
ROLE = "Handles the shop space: leases, rent due dates, landlord notices."
PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "facilities.md"
OUTPUT = AgentReport
MCP_TOOLS = frozenset({
    "list_open_tickets", "get_ticket", "get_lease_rent_due", "get_cash_position", "post_to_board",
})
