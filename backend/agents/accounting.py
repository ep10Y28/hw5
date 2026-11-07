"""Accounting: cash, invoices, margins; prepares payments and POs for human approval."""
from pathlib import Path
from ..models import AgentReport

NAME = "accounting"
ROLE = "Watches cash and invoices, checks margins, queues payments/purchase orders for HUMAN approval."
PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "accounting.md"
OUTPUT = AgentReport
MCP_TOOLS = frozenset({
    "list_open_tickets", "get_ticket",
    "get_cash_position", "get_invoice", "get_vendor_invoice_status", "get_lease_rent_due",
    "get_price_and_margin", "list_vendors", "list_approvals",
    "request_payment", "request_purchase_order", "post_to_board",
})
