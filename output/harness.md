# Campus Customs Agent Harness

This is the working reference for the Campus Customs multi-agent team (Boss, Inventory, Accounting, Facilities, Customer Service): what data it works on, the tools it may use, how the agents are built, how a person drives and supervises it, and the rules that keep it safe.

**Contents:** 1 Database tables · 2 The three tickets · 3 First MCP tools · 4 The five agents · 5 All MCP tools · 6 Safety and token limits · 7 API routes · 8 The dashboard · 9 Full run results

- **Original DB (never modified):** `data/campus_customs.db`
- **Working copy (agents read and write here):** `data/campus_customs_new.db`
- **Reset:** copy `campus_customs.db` over `campus_customs_new.db` before a full run.

---

## 1. Database tables

### desk (1 row)
| Field | Type | Notes |
|---|---|---|
| date_today | TEXT | The shop's "today" (`2026-08-31`) |
| notes | TEXT | Free-text desk notes (empty) |

**Why it matters:** Every agent measures "overdue" and "due soon" against `date_today`, not the real clock.

### tickets (3 rows)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Ticket number |
| type | TEXT | `customer_order`, `rent_notice`, `price_override` |
| requester | TEXT | Who opened the ticket |
| subject | TEXT | Short title |
| sku | TEXT | Product, if any → `inventory.sku` / `pricing.sku` |
| size | TEXT | Size, if any → `inventory.size` |
| qty | INTEGER | Units requested |
| lease_id | INTEGER FK | → `leases.id` |
| invoice_id | INTEGER FK | → `invoices.id` |
| status | TEXT | `open` now; agents move it toward resolved |
| notes | TEXT | The request in the requester's words |
| created_at | TEXT | Timestamp opened |

**Why it matters:** This is the board. Boss reads each ticket's `type` and its linked keys to decide which agents to send it to.

### inventory (10 rows, PK = sku + size)
| Field | Type | Notes |
|---|---|---|
| sku | TEXT | Product code |
| name | TEXT | Product name |
| size | TEXT | S/M/L/XL, or OS (one size) |
| qty | INTEGER | Units on hand |
| location | TEXT | Aisle |

**Why it matters:** Inventory checks stock by SKU and size here to find shortfalls. Two items are already at zero: `CC-TEE-WHITE` size S and `CC-MUG-CREST`.

### pricing (4 rows)
| Field | Type | Notes |
|---|---|---|
| sku | TEXT PK | Product code |
| unit_cost | REAL | What the shop pays per unit |
| list_price | REAL | What the customer pays |

**Why it matters:** Accounting uses cost against price to check margin before approving a discount and to cost out restock orders.

### vendors (3 rows)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Vendor id |
| name | TEXT | Bulldog Print Co / Elm City Gifts / QuickShip CT |
| specialty | TEXT | Apparel reprint / mugs and small goods / local courier |
| lead_days | INTEGER | Days to deliver (5 / 3 / 1) |

**Why it matters:** Inventory picks the restock vendor by `specialty` and gives the ETA from `lead_days`. Apparel can only come from Bulldog Print Co.

### invoices (1 row)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Invoice number |
| vendor_id | INTEGER FK | → `vendors.id` |
| amount | REAL | Amount owed |
| due_date | TEXT | Due date |
| status | TEXT | `open` (unpaid) or paid |
| description | TEXT | What it was for |

**Why it matters:** A vendor won't ship while it has an open unpaid invoice. Accounting has to clear these before Inventory can restock.

### leases (1 row)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Lease id |
| space_name | TEXT | Chapel Street shop |
| landlord | TEXT | Elm City Properties |
| monthly_rent | REAL | $2,400 |
| next_due | TEXT | `2026-09-02` |
| notes | TEXT | (empty) |

**Why it matters:** Facilities owns rent. `next_due` should move forward a month after rent is paid.

### cash_accounts (1 row)
| Field | Type | Notes |
|---|---|---|
| name | TEXT PK | `checking` |
| balance | REAL | $3,400 |
| date | TEXT | As-of date |

**Why it matters:** This is the only source of money. The pay tool has to refuse anything that would take `balance` below zero, and money never comes in.

### payments (0 rows)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Payment id |
| kind | TEXT | e.g. `invoice`, `rent` |
| ref_id | INTEGER | id of the invoice or lease paid |
| amount | REAL | Amount paid |
| account | TEXT | → `cash_accounts.name` |
| paid_at | TEXT | Date paid (use `desk.date_today`) |
| approved_by | TEXT | The human approver (required) |

**Why it matters:** This is the audit trail. Every approved payment writes a row here, decrements `cash_accounts.balance` and updates the invoice or lease it paid.

---

## 2. The three open tickets and how they link

**Today = 2026-08-31. Cash = $3,400.**

### Ticket 101: customer order (Tauhid Zaman): 1 × Bulldog Tee, size S
- `sku/size` → **inventory** `CC-TEE-WHITE` S: **qty 0** (stockout).
- `invoice_id 501` → **invoices** 501: **$840, due 2026-08-28, open** (3 days overdue), for "Rush reprint CC-TEE-WHITE S".
- `invoices.vendor_id 1` → **vendors** Bulldog Print Co (apparel, **5-day lead**).
- Chain: no stock → restock from Bulldog → Bulldog won't ship until invoice 501 is paid → paying it needs human approval.
- Agents: Boss → Inventory, Accounting (pay 501), Customer Service (delay message to the customer).

### Ticket 102: rent notice (Elm City Properties)
- `lease_id 1` → **leases** Chapel Street shop: **$2,400 due 2026-09-02** (2 days out).
- Agents: Boss → Facilities (confirm lease) → Accounting (prepare rent payment for human approval).

### Ticket 103: price override (Yale AI Club): 20 × hoodie, size M, bulk discount
- `sku/size` → **inventory** `CC-HOOD-NAVY` M: **qty 8**, so a **12-unit shortfall**.
- → **pricing**: cost $22, list $58, so a $36/unit margin (62%). There's room for a discount, but it needs a floor above cost.
- Restock is apparel → Bulldog Print Co, which is **blocked by the same open invoice 501**.
- Agents: Boss → Inventory (shortfall), Accounting (margin, PO cost), Customer Service (draft offer); Boss makes the final call on the discount.

### Cross-ticket tensions the agents must handle
- **Invoice 501 blocks two tickets** (101 and 103). Paying it unlocks Bulldog for both.
- **Cash is tight:** invoice 501 ($840) + rent ($2,400) = $3,240, which leaves **$160**. A 12-hoodie restock at cost (12 × $22 = $264) would not fit as well. The team has to prioritize, and the pay tool must refuse anything that overdraws.
- Every payment waits for a person's approval. Customer messages stay drafts on the board.

---

## 3. MCP tools (`mcp_server/server.py`)

All three tools read `data/campus_customs_new.db`, are read-only, return only database values (or `found: false`), and measure dates against `desk.date_today`.

### `check_stock_by_size(sku, size, qty_needed=0)`
- **Reads:** `inventory` (one row by the `sku` + `size` primary key).
- **Unlocks:** **Ticket 103.** The Yale AI Club wants 20 × `CC-HOOD-NAVY` size M. The tool returns `qty_on_hand: 8, shortfall: 12, can_fill_from_stock: false`. It also confirms ticket 101's `CC-TEE-WHITE` S is at 0.
- **Why it's the right tool:** Ticket 103 can't be priced or promised until Inventory knows exactly how many of the 20 M hoodies are on the shelf and how many must be reordered. Stock is tracked per size, so the lookup has to be by SKU *and* size.

### `get_vendor_invoice_status(vendor_id)`
- **Reads:** `vendors` (name, specialty, `lead_days`), `invoices` (open rows for that vendor), `desk` (today, for days overdue).
- **Unlocks:** **Ticket 101.** Tauhid's size-S tee is out of stock. Apparel comes from Bulldog Print Co (vendor 1), and the tool shows invoice 501 for $840 is open and 3 days overdue, so `will_ship: false`, with a 5-day lead time once it's cleared.
- **Why it's the right tool:** A vendor won't ship while it has an open unpaid invoice, so ticket 101's real blocker is invoice 501. This tool shows that blocker and the restock ETA in one call. The same answer also tells the team that ticket 103's hoodie restock is blocked by the same invoice.

### `get_lease_rent_due(lease_id)`
- **Reads:** `leases` (rent, `next_due`, landlord), `desk` (today), `cash_accounts` (checking balance).
- **Unlocks:** **Ticket 102.** Elm City Properties' rent notice links to lease 1. The tool returns `monthly_rent: 2400, next_due: 2026-09-02, days_until_due: 2, checking_balance: 3400, cash_covers_rent: true`.
- **Why it's the right tool:** Facilities needs to confirm from our own lease record, not the email, that the amount and due date in the notice are right and that cash covers it. That's what Accounting needs before preparing a rent payment for human approval. The tool is read-only and doesn't pay anything.

---

## 4. The agent team (`backend/`, PydanticAI)

Every agent uses **gpt-6-luna via Portkey** (`backend/llm.py`; the name is a constant with no override). Every agent gets its shop facts **only** from the MCP server, through a filtered view of one shared stdio connection (`backend/mcp_link.py`). Every agent has a `delegate` tool that can reach any other agent (full connectivity). Prompts are in `backend/prompts/<agent>.md`, roles and allowlists in `backend/agents/<agent>.py`, data types in `backend/models.py`, and the loop and audit in `backend/team.py` + `backend/audit.py`.

| Agent | Job | Output type | MCP tools it may call (allowlist) |
|---|---|---|---|
| **boss** | Reads each ticket, routes work, decides discounts and priorities, sets the final status | `TicketOutcome` | list_open_tickets, get_ticket, check_stock_by_size, get_vendor_invoice_status, get_lease_rent_due, get_price_and_margin, get_cash_position, list_approvals, post_to_board (*decision*/note), update_ticket_status (only boss may *resolve*) |
| **inventory** | Stock by SKU+size, shortfalls, which vendor can restock and when | `AgentReport` | list_open_tickets, get_ticket, check_stock_by_size, list_vendors, get_vendor_invoice_status, get_price_and_margin, post_to_board (note) |
| **accounting** | Cash, invoices, margins; queues payments and purchase orders **for human approval** | `AgentReport` | list_open_tickets, get_ticket, get_cash_position, get_invoice, get_vendor_invoice_status, get_lease_rent_due, get_price_and_margin, list_vendors, list_approvals, **request_payment**, **request_purchase_order**, post_to_board (note) |
| **facilities** | Leases and rent; checks notices against our lease record | `AgentReport` | list_open_tickets, get_ticket, get_lease_rent_due, get_cash_position, post_to_board (note) |
| **customer_service** | Customer drafts on the board (never sent) | `AgentReport` | list_open_tickets, get_ticket, check_stock_by_size, get_price_and_margin, list_vendors, post_to_board (*draft_message*) |

**Agent loop:** `CampusTeam.run_ticket(id)` starts Boss. Each agent runs through `agent.iter()`: model response → tool calls (MCP or `delegate`) → tool results → next model response, until it returns its structured output. A `delegate` call starts the other agent's loop, and its report comes back as the tool result. Every step is appended to `output/audit_trail.json` as it happens.

**Closing a ticket:** when Boss's run ends, the team's part is done and the ticket is marked `resolved`, either by Boss with `update_ticket_status` or by `team.run_ticket` on Boss's behalf. Anything still waiting on a person stays visible as pending approvals and in Boss's `needs_human` list.

**Expected routing for today's tickets:**
- 101 → inventory (tee S stockout; Bulldog blocked) → accounting (queue invoice 501, $840) → customer_service (delay draft).
- 102 → facilities (verify lease 1 against the notice) → accounting (queue $2,400 rent).
- 103 → inventory (8 of 20 on hand) → accounting (margin at the asked discount; PO blocked until invoice 501 is paid; cash cushion) → boss decides the discount → customer_service (offer draft).

---

## 5. All MCP tools (`mcp_server/server.py`, 17 tools)

New in Problem 5: two workflow tables, created in the working DB if missing. **approvals** holds money requests waiting for a human. **board** holds drafts, notes and decisions per ticket.

| Tool | Tier | Tables read → written | Ticket(s) |
|---|---|---|---|
| `check_stock_by_size` | read | inventory | 103, 101 |
| `get_vendor_invoice_status` | read | vendors, invoices, desk | 101 (and 103 restock) |
| `get_lease_rent_due` | read | leases, desk, cash_accounts | 102 |
| `list_open_tickets` | read | tickets, desk | all (Boss's board) |
| `list_tickets` | read | tickets, desk | all (dashboard list, open + resolved; added in P7) |
| `get_ticket` | read | tickets, board, approvals | all |
| `get_price_and_margin` | read | pricing | 103 (discount math) |
| `list_vendors` | read | vendors, invoices | 101, 103 (pick restock vendor) |
| `get_invoice` | read | invoices, vendors, desk | 101 (invoice 501) |
| `get_cash_position` | read | cash_accounts, invoices, leases, approvals, desk | 101, 102, 103 (shared cash) |
| `list_approvals` | read | approvals | all |
| `request_payment` | workflow (no money moves) | invoices / leases, cash_accounts, approvals → **approvals** | 101 (invoice 501), 102 (rent) |
| `request_purchase_order` | workflow (no money moves) | vendors, invoices, inventory, pricing, cash_accounts, approvals → **approvals** | 103 (12 hoodies), 101 |
| `post_to_board` | workflow | tickets → **board** | all |
| `update_ticket_status` | workflow | tickets → **tickets**, **board** | all |
| `record_human_decision` | **human only** | approvals → **approvals** | approval button |
| `execute_approved_payment` | **human only** | approvals, cash_accounts, invoices, leases → **payments**, **cash_accounts**, **invoices** / **leases**, **approvals** | after a human approves |

---

## 6. Safety: guardrails and token limits

### Guardrails for real customers and real money
- **A human approves every payment.** Agents can only *queue* requests. `record_human_decision` and `execute_approved_payment` are filtered out of every agent's toolset (`view_for` raises an error if one is ever added) and are blocked again in `stamp_and_guard`. The approver must be a person's name, not an agent's. Payment rows carry `approved_by`.
- **Agents never supply dollar amounts.** Invoice amount, rent and qty × unit_cost are read from the DB inside the tool.
- **No negative balances.** Requests are refused if cash minus money already reserved by pending/approved requests can't cover them. `execute_approved_payment` re-checks inside a single DB transaction and marks the request `refused` if cash is short. Cash only goes out.
- **The vendor-block rule is in code.** `request_purchase_order` and `execute_approved_payment` both refuse while the vendor has an open invoice.
- **One payment per bill.** Duplicate requests for the same invoice or lease are refused, and an executed request can't be paid twice.
- **Identity is stamped by code.** `requested_by` / `author` / `updated_by` are overwritten with the calling agent's name, so an agent can't act as another.
- **Role limits:** each agent sees only its allowlist. Only customer_service writes customer drafts, only boss posts decisions, and only boss resolves tickets.
- **Nothing is sent outside the shop.** Customer and landlord messages are board drafts with `sent: false`. There is no email or vendor tool.
- **No invented facts.** Tools return `found: false` instead of guessing, and prompts require every number to come from a tool result with its source table. Customer service must not reveal internal finances (invoices, cash, margins).
- **Our records over emails.** Facilities checks notices against the lease table and flags mismatches instead of trusting the email.
- **Safe to reset.** Agents only touch `campus_customs_new.db`. The original stays untouched for resets, and the MCP server won't silently create an empty DB.
- **Append-only audit.** Every loop step, tool call/result, delegation and blocked action goes to `output/audit_trail.json` with run ids, so any decision can be traced back.

- **Desk-level guardrails** (backend + dashboard):
  - Only the approve route moves cash, and it rejects an agent name as approver. The dashboard won't let you sign without a name.
  - Only one agent run at a time, because runs share one database and one cash balance.
  - Reset is refused during a run, takes two clicks, and never wipes the audit trail.
  - CORS allows only the local dashboard origins.
  - Resolved tickets can't be re-run.
- **What the full run showed (Problem 9):**
  - 0 guardrail blocks: the agents stayed inside their roles.
  - No payment happened without Eddie's signature.
  - On ticket 103 the cash limit worked as designed: Accounting refused to queue a $264 PO it couldn't fund.
  - One gap to fix next: Accounting re-asked Inventory a question Boss had already asked (duplicate work, about 10 extra steps). A real shop would pass teammates' reports along with each hand-off, or block a second identical delegation per ticket.

### Limits that keep token use in check (per ticket, shared by every agent on it)
- `UsageLimits`: **40 model requests, 60 tool calls, 150k total tokens**. One shared usage counter covers all agents, so delegation can't multiply the budget. Exceeding it stops the ticket and is logged.
- **Max delegation depth 2** (Boss → A → B), **max 8 delegations per ticket**, **no self-delegation and no cycles** (can't delegate back to anyone already in the chain).
- **`max_tokens` 4,000 per model reply**, `retries=2` on bad tool calls or output.
- **One model only** (gpt-6-luna), so there's no accidental fallback to a pricier model.
- **Small tool payloads.** Tools return only the needed fields, and audit fields are cut to 600 characters.
- **Prompts limit waste:** don't repeat a tool call with the same arguments, make self-contained hand-offs, and delegate once per specialist.
- **Observed cost in the full run:** 101 = 17 requests, about 46k tokens · 102 = 13 requests, about 37k tokens · 103 = 23 requests, about 65k tokens. All under the 40-request / 150k-token cap. Ticket 103 cost the most because of the duplicate Inventory hand-off.

---

## 7. Backend routes (`backend/main.py`, FastAPI)

Start with `cd backend && uvicorn main:app --reload --port 8000`. Interactive docs are at `/docs`. CORS allows the Vite dashboard at `http://localhost:5173` (and :3000). Every route reads and writes through the MCP server, and only the approve route moves cash.

- `GET /api/health`: server status, whether the agent team loaded, whether a run is in progress.
- `GET /api/tickets`: all tickets with status and `state` = open / resolved (MCP `list_tickets`).
- `GET /api/tickets/{id}`: one ticket with its board posts (drafts, notes, decisions) and approvals (MCP `get_ticket`).
- `POST /api/tickets/{id}/run`: runs the agent team (Boss first) on that ticket in the background and returns a `ticket_run_id` (`?wait=true` blocks until done). One run at a time, and resolved tickets are refused. When the run finishes, the ticket is marked **resolved** (the team's part is done; anything still waiting on a person stays in approvals and Boss's `needs_human`).
- `GET /api/runs`: agent runs since the server started, plus the active one (the dashboard reconnects to a run after a page reload).
- `GET /api/runs/{ticket_run_id}`: a run's status (queued / running / done / error) and Boss's final `TicketOutcome`.
- `GET /api/events?since=&ticket_id=&ticket_run_id=&limit=`: recent audit-trail events (what each agent said, its tool calls and results, delegations); poll with `next_since`.
- `GET /api/tickets/{id}/summary`: a short per-agent recap of the latest run on a ticket (what each agent concluded, tools used, hand-offs, approvals and board posts created).
- `GET /api/approvals?status=pending`: payments and purchase orders the agents prepared for a human, with payee and memo filled in from the DB for the cheque view.
- `POST /api/approvals/{id}/approve` `{approver, note}`: a human approves and the request is **paid** (MCP `record_human_decision` + `execute_approved_payment`). Updates payments, cash and the invoice/lease, and refuses an agent name or anything that would overdraw cash.
- `POST /api/approvals/{id}/reject` `{approver, note}`: a human rejects a request. No money moves.
- `GET /api/cash`: current checking balance from `cash_accounts`, plus money reserved by pending approvals.
- `POST /api/reset`: copies `campus_customs.db` over the working copy for a fresh run (refused during a run; the audit trail is kept).

---

## 8. The dashboard (`frontend/`, React + Vite + TypeScript)

Start with `cd frontend && npm install && npm run dev`, which opens http://localhost:5173 and calls the backend at `http://localhost:8000` (`src/api.ts`). Design rationale is in `output/design.md`.

| Area | What it shows | Routes it uses |
|---|---|---|
| Header **till** | Checking balance (`cash_accounts`), money promised to pending approvals, and what's free. Counts down with a −$ flash and sparkline when a payment is signed | `GET /api/cash` |
| Left: **ticket spike** | All tickets as paper stubs, open or with a RESOLVED stamp. Select one, then **Hand to the team →** | `GET /api/tickets`, `POST /api/tickets/{id}/run` |
| Center: **agent seats** | The five agents (each with its own colour, monogram and voice) and their live state: idle, working, waiting on a hand-off, or done | `GET /api/events` (polled every 1.2 s), `GET /api/runs/{id}` |
| Center: **Live wire** | Transcript of the run: what each agent said, each tool call (plain verb + real tool name + args), results, hand-offs with the exact task text, guardrail blocks | `GET /api/events?since=…&ticket_run_id=…` |
| Center: **Recap** | Boss's call, "Left for a person", one card per agent (summary, tools, hand-offs, ids created), customer drafts stamped DRAFT · NOT SENT | `GET /api/tickets/{id}/summary`, `GET /api/tickets/{id}` |
| Right: **Needs your signature** | Pending payments and POs drawn as cheques (payee, amount, memo, preparing agent). **Sign & pay** or **Void**, and signed ones show PAID with the signer's name | `GET /api/approvals`, `POST /api/approvals/{id}/approve`, `/reject` |
| Header **Reset shop** | Restores the original database for a fresh run (two clicks) | `POST /api/reset` |

---

## 9. Full run results (Problem 9)

The working DB was reset at 2026-11-07 13:56:10Z, so checking started at **$3,400.00**. Tickets ran 101 → 102 → 103 from the dashboard, every agent on gpt-6-luna. All three ended **resolved**.

| Ticket | Agents (Boss called) | Human approval | Cash |
|---|---|---|---|
| 101 Bulldog tee | Inventory + Accounting + Customer Service (parallel) | #1 invoice 501 → Bulldog Print Co, approved by Eddie Peyton | −$840.00 → $2,560.00 |
| 102 Rent due | Facilities, then Accounting | #2 rent, lease 1 → Elm City Properties, approved by Eddie Peyton | −$2,400.00 → $160.00 |
| 103 Bulk hoodies | Inventory + Accounting (+ Accounting → Inventory) + Customer Service | none. The $264 restock exceeds $160, so no PO was queued | $0.00 → $160.00 |

**Ending checking: $160.00**, which equals `cash_accounts.balance` in `data/campus_customs_new.db` ($3,400 − $840 − $2,400). Details: `output/desk_tickets.html` (Expected vs Actual per ticket, plus the Cash tab), `output/resolved_tickets.json`, `output/resolved_board.html`, and the run's steps in `output/audit_trail.json`.
