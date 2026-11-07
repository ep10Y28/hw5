"""Customer Service: drafts messages for customers (never sends)."""
from pathlib import Path
from ..models import AgentReport

NAME = "customer_service"
ROLE = "Drafts customer messages to the board (never sent) using only confirmed facts."
PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "customer_service.md"
OUTPUT = AgentReport
MCP_TOOLS = frozenset({
    "list_open_tickets", "get_ticket", "check_stock_by_size", "get_price_and_margin",
    "list_vendors", "post_to_board",
})
