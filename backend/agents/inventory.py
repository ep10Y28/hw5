"""Inventory: stock by SKU and size, shortfalls, which vendor can restock."""
from pathlib import Path
from ..models import AgentReport

NAME = "inventory"
ROLE = "Checks stock by SKU+size, finds shortfalls, picks the vendor that can restock and its ETA."
PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "inventory.md"
OUTPUT = AgentReport
MCP_TOOLS = frozenset({
    "list_open_tickets", "get_ticket",
    "check_stock_by_size", "list_vendors", "get_vendor_invoice_status", "get_price_and_margin",
    "post_to_board",
})
