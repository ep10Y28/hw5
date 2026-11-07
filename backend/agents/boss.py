"""Boss: reads each ticket, routes work, makes the final call."""
from pathlib import Path
from ..models import TicketOutcome

NAME = "boss"
ROLE = "Reads tickets, decides who works on them, makes final calls (discounts, priorities, resolve)."
PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "boss.md"
OUTPUT = TicketOutcome
MCP_TOOLS = frozenset({
    "list_open_tickets", "get_ticket",
    "check_stock_by_size", "get_vendor_invoice_status", "get_lease_rent_due",
    "get_price_and_margin", "get_cash_position", "list_approvals",
    "post_to_board", "update_ticket_status",
})
