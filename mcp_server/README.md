# Campus Customs MCP Server

**What it's for:** This is the shared toolbox, and the only data layer, for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Agents, and the FastAPI backend (`backend/main.py`), never query the database directly. They call these tools, so every agent sees the same facts, only facts that are in the database, and the shop rules (human approval, no negative cash, vendor blocks) are enforced in one place.

**Database:** `data/campus_customs_new.db`, the working copy. The original `data/campus_customs.db` is never modified. Copy it over the working copy to reset. You can override the path with the `CAMPUS_DB_PATH` environment variable. If the file is missing, the server raises an error instead of creating an empty DB. On first use it adds two workflow tables if they're missing: `approvals` (money requests waiting for a human) and `board` (drafts, notes and decisions per ticket).

**Built with:** [FastMCP](https://gofastmcp.com). Start it with `python mcp_server/server.py` (stdio). It's registered for Claude Code in `/.mcp.json`. The backend connects to it from `backend/mcp_link.py`.

## Tools (17)

### Read: facts only, any agent
| Tool | Reads | Returns |
|---|---|---|
| `check_stock_by_size(sku, size, qty_needed=0)` | inventory | Units on hand for one SKU+size, and the shortfall vs `qty_needed` |
| `get_vendor_invoice_status(vendor_id)` | vendors, invoices, desk | Lead time, open invoices with days overdue, `will_ship` |
| `get_lease_rent_due(lease_id)` | leases, desk, cash_accounts | Rent, due date, days until due, whether checking covers it |
| `list_open_tickets()` | tickets, desk | Every unresolved ticket + today |
| `list_tickets()` | tickets, desk | Every ticket, open and resolved, with `is_open` (dashboard) |
| `get_ticket(ticket_id)` | tickets, board, approvals | One ticket with its board posts and approvals |
| `get_price_and_margin(sku, qty=1, discount_pct=0)` | pricing | Cost, list, discounted price, margins, order totals, `below_cost`, max discount before a loss |
| `list_vendors()` | vendors, invoices | All vendors with specialty, lead_days, open balance, `will_ship` |
| `get_invoice(invoice_id)` | invoices, vendors, desk | One invoice with vendor and days overdue |
| `get_cash_position()` | cash_accounts, invoices, leases, approvals, desk | Balance, obligations, money reserved by pending requests, what's left |
| `list_approvals(status="pending")` | approvals | Approval requests by status |

### Workflow: agents queue and record, never move money
| Tool | Writes | Notes |
|---|---|---|
| `request_payment(kind, ref_id, ticket_id, reason, requested_by)` | approvals | `invoice` or `rent`. Amount read from the DB. Refuses duplicates, paid invoices, and anything cash can't cover |
| `request_purchase_order(vendor_id, sku, size, qty, ticket_id, reason, requested_by)` | approvals | Amount = qty × unit_cost. Refuses if the vendor has an open invoice or cash is short. Returns the expected arrival |
| `post_to_board(ticket_id, kind, author, body, recipient="")` | board | `draft_message` / `note` / `decision`. Nothing is ever sent |
| `update_ticket_status(ticket_id, status, note, updated_by)` | tickets, board | Only `boss` may set `resolved` |

### Human only: never given to agents (dashboard approval button)
| Tool | Writes | Notes |
|---|---|---|
| `record_human_decision(approval_id, decision, approver, note="")` | approvals | `approved` / `rejected`. The approver must be a person, not an agent name |
| `execute_approved_payment(approval_id)` | payments, cash_accounts, invoices / leases, approvals | One transaction. Requires `approved`. Refuses if cash would go negative. Marks the invoice paid or moves the lease's next_due forward a month |

All dates are measured against `desk.date_today`. When a record doesn't exist, tools return `found: false`.
