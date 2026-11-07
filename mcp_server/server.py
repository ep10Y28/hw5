"""Campus Customs MCP server.

Every agent on the Campus Customs team (Boss, Inventory, Accounting,
Facilities, Customer Service) gets its tools from this server.

The server talks ONLY to the working copy of the shop database,
data/campus_customs_new.db. The original data/campus_customs.db is never
touched, so it can be copied back over the working copy to reset.

Ground rules for every tool:
- Only return what is in the database. Never invent or guess values.
- If a record is not found, say so plainly instead of making one up.
- "Today" is desk.date_today, not the computer clock.
- Money amounts are ALWAYS read from the database (invoice amount, lease
  rent, unit cost). No tool accepts a dollar amount from an agent.
- No payment leaves the shop without a human approval recorded in the
  approvals table. The pay tool refuses if cash would go negative.
- Customer messages are saved as drafts on the board. Nothing is sent.

Tool tiers
- Read tools ........ any agent may call (facts only).
- Workflow tools .... agents call to queue approvals, post drafts/notes,
                      and move ticket status. They never move money.
- Human-only tools .. record_human_decision, execute_approved_payment.
                      The backend never gives these to an agent; only the
                      approval endpoint behind the dashboard calls them.

Workflow tables (created here if missing; a reset removes them):
- approvals: payment / purchase-order requests waiting for a human.
- board:     drafts, notes and decisions posted against a ticket.

Run (later problems): python mcp_server/server.py
"""

from __future__ import annotations

import os
import sqlite3
import calendar
from datetime import date, datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("CAMPUS_DB_PATH", ROOT / "data" / "campus_customs_new.db"))

mcp = FastMCP("campus-customs")


# ---------------------------------------------------------------- helpers

def _connect() -> sqlite3.Connection:
    """Open the working DB. mode=rw so a wrong path errors instead of
    silently creating an empty database."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Working database not found at {DB_PATH}. "
            "Copy data/campus_customs.db to data/campus_customs_new.db first."
        )
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    conn.executescript(WORKFLOW_SCHEMA)  # approvals + board, if missing (survives a reset)
    return conn


def _today(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise ValueError("desk table has no date_today row.")
    return row["date_today"]


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


def _add_month(day: str) -> str:
    d = date.fromisoformat(day[:10])
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1])).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}
TICKET_STATUSES = {"open", "in_progress", "waiting_approval", "blocked", "resolved"}
BOARD_KINDS = {"draft_message", "note", "decision"}

WORKFLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER,                  -- invoices.id / leases.id / vendors.id
    ticket_id INTEGER,
    vendor_id INTEGER,
    sku TEXT, size TEXT, qty INTEGER,
    amount REAL NOT NULL,            -- always computed from the DB
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,      -- agent name
    requested_at TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending | approved | rejected | executed | refused
    decided_by TEXT, decided_at TEXT, decision_note TEXT,
    payment_id INTEGER
);
CREATE TABLE IF NOT EXISTS board (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    kind TEXT NOT NULL,              -- draft_message | note | decision
    author TEXT NOT NULL,
    recipient TEXT,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _ensure_workflow_tables() -> None:
    _connect().close()


def _checking_balance(conn: sqlite3.Connection) -> float | None:
    row = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()
    return None if row is None else row["balance"]


def _pending_total(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM approvals WHERE status IN ('pending', 'approved')"
    ).fetchone()
    return round(row[0], 2)


# ---------------------------------------------------------------- tools

@mcp.tool
def check_stock_by_size(sku: str, size: str, qty_needed: int = 0) -> dict:
    """Check how many units of a SKU are on hand in one size.

    Reads: inventory.
    Pass qty_needed (e.g. a ticket's qty) to get the shortfall.
    Used by Inventory for ticket 103 (20 hoodies, size M) and ticket 101.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory "
            "WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if row is None:
            sizes = [r["size"] for r in conn.execute(
                "SELECT size FROM inventory WHERE sku = ?", (sku,))]
            return {
                "found": False,
                "sku": sku,
                "size": size,
                "message": "No inventory row for this SKU and size.",
                "sizes_on_record_for_sku": sizes,
            }
        on_hand = row["qty"]
        result = {
            "found": True,
            "sku": row["sku"],
            "name": row["name"],
            "size": row["size"],
            "qty_on_hand": on_hand,
            "location": row["location"],
        }
        if qty_needed:
            result["qty_needed"] = qty_needed
            result["shortfall"] = max(qty_needed - on_hand, 0)
            result["can_fill_from_stock"] = on_hand >= qty_needed
        return result


@mcp.tool
def get_vendor_invoice_status(vendor_id: int) -> dict:
    """Show a vendor's lead time and any OPEN (unpaid) invoices.

    Reads: vendors, invoices, desk.
    A vendor will not ship new product while it has an open unpaid invoice,
    so this tells Inventory/Accounting whether a restock is blocked.
    Used for ticket 101 (invoice 501 to Bulldog Print Co blocks the tee reprint).
    """
    with _connect() as conn:
        today = _today(conn)
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?",
            (vendor_id,),
        ).fetchone()
        if vendor is None:
            return {"found": False, "vendor_id": vendor_id,
                    "message": "No vendor with this id."}
        open_invoices = []
        for inv in conn.execute(
            "SELECT id, amount, due_date, status, description FROM invoices "
            "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
            (vendor_id,),
        ):
            days_overdue = _days_between(inv["due_date"], today)
            open_invoices.append({
                "invoice_id": inv["id"],
                "amount": inv["amount"],
                "due_date": inv["due_date"],
                "status": inv["status"],
                "description": inv["description"],
                "days_overdue": max(days_overdue, 0),
                "is_overdue": days_overdue > 0,
            })
        return {
            "found": True,
            "today": today,
            "vendor_id": vendor["id"],
            "vendor_name": vendor["name"],
            "specialty": vendor["specialty"],
            "lead_days": vendor["lead_days"],
            "open_invoices": open_invoices,
            "open_balance": round(sum(i["amount"] for i in open_invoices), 2),
            "will_ship": len(open_invoices) == 0,
        }


@mcp.tool
def get_lease_rent_due(lease_id: int) -> dict:
    """Show a lease's monthly rent, due date, days until due, and whether
    checking cash covers it.

    Reads: leases, desk, cash_accounts.
    Read-only: it does NOT pay rent (payments need human approval).
    Used by Facilities for ticket 102 (Chapel Street rent notice).
    """
    with _connect() as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
            "FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"found": False, "lease_id": lease_id,
                    "message": "No lease with this id."}
        cash = conn.execute(
            "SELECT name, balance FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()
        days_until_due = _days_between(today, lease["next_due"])
        result = {
            "found": True,
            "today": today,
            "lease_id": lease["id"],
            "space_name": lease["space_name"],
            "landlord": lease["landlord"],
            "monthly_rent": lease["monthly_rent"],
            "next_due": lease["next_due"],
            "days_until_due": days_until_due,
            "is_overdue": days_until_due < 0,
            "notes": lease["notes"],
        }
        if cash is not None:
            result["checking_balance"] = cash["balance"]
            result["cash_covers_rent"] = cash["balance"] >= lease["monthly_rent"]
        return result


# ================================================================ read tools

@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that is not resolved, with its type, requester,
    linked sku/size/qty, lease_id and invoice_id, plus the shop's today.

    Reads: tickets, desk. Boss calls this first to see the board.
    """
    with _connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY id")]
        return {"today": _today(conn), "count": len(rows), "tickets": rows}


@mcp.tool
def list_tickets() -> dict:
    """Every ticket (open AND resolved) with its status and an is_open flag.

    Reads: tickets, desk. Used by the dashboard's ticket list.
    """
    with _connect() as conn:
        rows = [{**dict(r), "is_open": r["status"] != "resolved"}
                for r in conn.execute("SELECT * FROM tickets ORDER BY id")]
        return {"today": _today(conn), "count": len(rows), "tickets": rows}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket with everything posted to the board for it and any
    approvals queued for it.

    Reads: tickets, board, approvals.
    """
    with _connect() as conn:
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"found": False, "ticket_id": ticket_id, "message": "No ticket with this id."}
        board = [dict(r) for r in conn.execute(
            "SELECT * FROM board WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
        approvals = [dict(r) for r in conn.execute(
            "SELECT * FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
        return {"found": True, "today": _today(conn), "ticket": dict(t),
                "board": board, "approvals": approvals}


@mcp.tool
def get_price_and_margin(sku: str, qty: int = 1, discount_pct: float = 0.0) -> dict:
    """Unit cost, list price and margin for a SKU, and what a proposed
    discount does to price, margin and order total.

    Reads: pricing. Flags any discount that would sell below cost.
    Used by Accounting for ticket 103 (bulk hoodie discount).
    """
    if qty < 1:
        return {"ok": False, "message": "qty must be at least 1."}
    if not 0 <= discount_pct < 100:
        return {"ok": False, "message": "discount_pct must be between 0 and 100."}
    with _connect() as conn:
        p = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if p is None:
            return {"found": False, "sku": sku, "message": "No pricing row for this SKU."}
        cost, lst = p["unit_cost"], p["list_price"]
        price = round(lst * (1 - discount_pct / 100), 2)
        max_discount_at_cost = round((1 - cost / lst) * 100, 2)
        return {
            "found": True, "sku": sku, "qty": qty,
            "unit_cost": cost, "list_price": lst,
            "list_margin_per_unit": round(lst - cost, 2),
            "list_margin_pct": round((lst - cost) / lst * 100, 2),
            "discount_pct": discount_pct,
            "discounted_unit_price": price,
            "discounted_margin_per_unit": round(price - cost, 2),
            "discounted_margin_pct": round((price - cost) / price * 100, 2) if price else None,
            "order_revenue": round(price * qty, 2),
            "order_cost": round(cost * qty, 2),
            "order_margin": round((price - cost) * qty, 2),
            "below_cost": price < cost,
            "max_discount_pct_before_loss": max_discount_at_cost,
        }


@mcp.tool
def list_vendors() -> dict:
    """All vendors with specialty, lead_days, open invoice count/balance and
    whether they will ship today.

    Reads: vendors, invoices. Inventory uses this to pick a restock vendor
    by specialty (apparel -> 'apparel reprint', mugs -> 'mugs and small goods').
    """
    with _connect() as conn:
        out = []
        for v in conn.execute("SELECT * FROM vendors ORDER BY id"):
            inv = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM invoices "
                "WHERE vendor_id = ? AND status = 'open'", (v["id"],)).fetchone()
            out.append({**dict(v), "open_invoice_count": inv[0],
                        "open_balance": round(inv[1], 2), "will_ship": inv[0] == 0})
        return {"vendors": out}


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """One invoice with its vendor and days overdue versus the shop's today.

    Reads: invoices, vendors, desk.
    """
    with _connect() as conn:
        today = _today(conn)
        inv = conn.execute(
            "SELECT i.*, v.name AS vendor_name, v.lead_days FROM invoices i "
            "JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (invoice_id,)).fetchone()
        if inv is None:
            return {"found": False, "invoice_id": invoice_id, "message": "No invoice with this id."}
        overdue = _days_between(inv["due_date"], today)
        return {"found": True, "today": today, **dict(inv),
                "days_overdue": max(overdue, 0), "is_overdue": overdue > 0}


@mcp.tool
def get_cash_position() -> dict:
    """Checking balance, every open invoice and upcoming rent, money already
    tied up in pending/approved requests, and cash left after all of it.

    Reads: cash_accounts, invoices, leases, approvals, desk.
    Accounting calls this before queuing any payment. Cash only goes out.
    """
    with _connect() as conn:
        today = _today(conn)
        bal = _checking_balance(conn)
        invoices = [{**dict(r), "days_overdue": max(_days_between(r["due_date"], today), 0)}
                    for r in conn.execute(
                        "SELECT id, vendor_id, amount, due_date, description FROM invoices "
                        "WHERE status = 'open' ORDER BY due_date")]
        leases = [{**dict(r), "days_until_due": _days_between(today, r["next_due"])}
                  for r in conn.execute(
                      "SELECT id, space_name, landlord, monthly_rent, next_due FROM leases ORDER BY next_due")]
        reserved = _pending_total(conn)
        obligations = round(sum(i["amount"] for i in invoices) + sum(l["monthly_rent"] for l in leases), 2)
        return {
            "today": today, "checking_balance": bal,
            "open_invoices": invoices, "leases": leases,
            "open_obligations_total": obligations,
            "reserved_in_pending_or_approved_requests": reserved,
            "available_after_reserved": None if bal is None else round(bal - reserved, 2),
            "left_if_all_obligations_paid": None if bal is None else round(bal - obligations, 2),
        }


# ============================================================ workflow tools

@mcp.tool
def request_payment(kind: str, ref_id: int, ticket_id: int, reason: str, requested_by: str) -> dict:
    """Queue a payment for HUMAN approval. Does not move money.

    kind='invoice' -> ref_id is invoices.id (amount = invoice amount)
    kind='rent'    -> ref_id is leases.id   (amount = monthly_rent)
    The amount is always read from the database. Refuses duplicates, paid
    invoices, and requests that cash cannot cover (including what is
    already reserved by other pending requests).
    Reads: invoices / leases, cash_accounts, approvals. Writes: approvals.
    """
    if kind not in {"invoice", "rent"}:
        return {"ok": False, "message": "kind must be 'invoice' or 'rent'."}
    if requested_by not in AGENT_NAMES:
        return {"ok": False, "message": f"requested_by must be one of {sorted(AGENT_NAMES)}."}
    if not reason.strip():
        return {"ok": False, "message": "A reason is required."}
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"ok": False, "message": f"No ticket {ticket_id}."}
        if kind == "invoice":
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if row is None:
                return {"ok": False, "message": f"No invoice {ref_id}."}
            if row["status"] != "open":
                return {"ok": False, "message": f"Invoice {ref_id} is '{row['status']}', not open."}
            amount, vendor_id = row["amount"], row["vendor_id"]
        else:
            row = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if row is None:
                return {"ok": False, "message": f"No lease {ref_id}."}
            amount, vendor_id = row["monthly_rent"], None
        dup = conn.execute(
            "SELECT id, status FROM approvals WHERE kind = ? AND ref_id = ? "
            "AND status IN ('pending', 'approved')", (kind, ref_id)).fetchone()
        if dup:
            return {"ok": False, "message": f"Already queued as approval {dup['id']} ({dup['status']}).",
                    "approval_id": dup["id"]}
        bal = _checking_balance(conn) or 0.0
        reserved = _pending_total(conn)
        if amount > bal - reserved:
            return {"ok": False, "refused": True,
                    "message": "Not enough cash once other pending requests are counted.",
                    "amount": amount, "checking_balance": bal, "already_reserved": reserved}
        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, ticket_id, vendor_id, amount, reason, "
            "requested_by, requested_at, status) VALUES (?,?,?,?,?,?,?,?, 'pending')",
            (kind, ref_id, ticket_id, vendor_id, amount, reason.strip(), requested_by, _now()))
        return {"ok": True, "approval_id": cur.lastrowid, "status": "pending",
                "kind": kind, "ref_id": ref_id, "amount": amount,
                "cash_after_if_approved": round(bal - reserved - amount, 2),
                "message": "Queued for human approval. No money has moved."}


@mcp.tool
def request_purchase_order(vendor_id: int, sku: str, size: str, qty: int,
                           ticket_id: int, reason: str, requested_by: str) -> dict:
    """Queue a restock purchase order for HUMAN approval. Does not move money.

    Amount = qty x pricing.unit_cost. Refuses if the vendor still has an
    open unpaid invoice (it will not ship), if sku/size is unknown, or if
    cash cannot cover it after other pending requests. Returns the
    expected arrival date (today + vendors.lead_days).
    Reads: vendors, invoices, inventory, pricing, cash_accounts, approvals.
    Writes: approvals.
    """
    if qty < 1:
        return {"ok": False, "message": "qty must be at least 1."}
    if requested_by not in AGENT_NAMES:
        return {"ok": False, "message": f"requested_by must be one of {sorted(AGENT_NAMES)}."}
    with _connect() as conn:
        today = _today(conn)
        v = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if v is None:
            return {"ok": False, "message": f"No vendor {vendor_id}."}
        if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
            return {"ok": False, "message": f"No inventory row for {sku} size {size}."}
        p = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if p is None:
            return {"ok": False, "message": f"No pricing for {sku}."}
        open_inv = [dict(r) for r in conn.execute(
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'", (vendor_id,))]
        if open_inv:
            return {"ok": False, "blocked": True,
                    "message": f"{v['name']} will not ship while invoice(s) are open. Pay them first.",
                    "open_invoices": open_inv}
        amount = round(qty * p["unit_cost"], 2)
        bal = _checking_balance(conn) or 0.0
        reserved = _pending_total(conn)
        if amount > bal - reserved:
            return {"ok": False, "refused": True,
                    "message": "Not enough cash once other pending requests are counted.",
                    "amount": amount, "checking_balance": bal, "already_reserved": reserved}
        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, ticket_id, vendor_id, sku, size, qty, amount, "
            "reason, requested_by, requested_at, status) VALUES "
            "('purchase_order', ?,?,?,?,?,?,?,?,?,?, 'pending')",
            (vendor_id, ticket_id, vendor_id, sku, size, qty, amount, reason.strip(), requested_by, _now()))
        arrival = date.fromordinal(date.fromisoformat(today).toordinal() + v["lead_days"])
        return {"ok": True, "approval_id": cur.lastrowid, "status": "pending",
                "vendor": v["name"], "sku": sku, "size": size, "qty": qty,
                "unit_cost": p["unit_cost"], "amount": amount,
                "expected_arrival": arrival.isoformat(),
                "message": "Queued for human approval. No money has moved."}


@mcp.tool
def list_approvals(status: str = "pending") -> dict:
    """List approval requests by status (pending, approved, rejected,
    executed, refused, or 'all').

    Reads: approvals.
    """
    with _connect() as conn:
        if status == "all":
            rows = conn.execute("SELECT * FROM approvals ORDER BY id")
        else:
            rows = conn.execute("SELECT * FROM approvals WHERE status = ? ORDER BY id", (status,))
        rows = [dict(r) for r in rows]
        return {"status": status, "count": len(rows), "approvals": rows}


@mcp.tool
def post_to_board(ticket_id: int, kind: str, author: str, body: str, recipient: str = "") -> dict:
    """Post a draft customer message, an internal note, or a decision to a
    ticket's board. Drafts are NEVER sent; a human sends them.

    kind: draft_message | note | decision. Writes: board.
    """
    if kind not in BOARD_KINDS:
        return {"ok": False, "message": f"kind must be one of {sorted(BOARD_KINDS)}."}
    if author not in AGENT_NAMES:
        return {"ok": False, "message": f"author must be one of {sorted(AGENT_NAMES)}."}
    if not body.strip():
        return {"ok": False, "message": "body is empty."}
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"ok": False, "message": f"No ticket {ticket_id}."}
        cur = conn.execute(
            "INSERT INTO board (ticket_id, kind, author, recipient, body, created_at) VALUES (?,?,?,?,?,?)",
            (ticket_id, kind, author, recipient or None, body.strip()[:4000], _now()))
        return {"ok": True, "board_id": cur.lastrowid, "ticket_id": ticket_id, "kind": kind,
                "sent": False, "message": "Saved to the board. Nothing was sent."}


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, note: str, updated_by: str) -> dict:
    """Move a ticket to open | in_progress | waiting_approval | blocked | resolved
    and log a note on the board. Only Boss should resolve tickets.

    Writes: tickets (status), board (note).
    """
    if status not in TICKET_STATUSES:
        return {"ok": False, "message": f"status must be one of {sorted(TICKET_STATUSES)}."}
    if updated_by not in AGENT_NAMES:
        return {"ok": False, "message": f"updated_by must be one of {sorted(AGENT_NAMES)}."}
    if status == "resolved" and updated_by != "boss":
        return {"ok": False, "message": "Only boss may resolve a ticket."}
    with _connect() as conn:
        t = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"ok": False, "message": f"No ticket {ticket_id}."}
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.execute(
            "INSERT INTO board (ticket_id, kind, author, body, created_at) VALUES (?, 'note', ?, ?, ?)",
            (ticket_id, updated_by, f"Status {t['status']} -> {status}. {note.strip()}", _now()))
        return {"ok": True, "ticket_id": ticket_id, "old_status": t["status"], "new_status": status}


# ============================================ human-only tools (never given to agents)

@mcp.tool
def record_human_decision(approval_id: int, decision: str, approver: str, note: str = "") -> dict:
    """HUMAN ONLY. Record a person's approve/reject on a pending request.

    The backend calls this from the dashboard's approval button. It is
    filtered out of every agent's toolset. approver must be a person's
    name, not an agent name. Writes: approvals.
    """
    if decision not in {"approved", "rejected"}:
        return {"ok": False, "message": "decision must be 'approved' or 'rejected'."}
    if not approver.strip() or approver.strip().lower() in AGENT_NAMES:
        return {"ok": False, "message": "approver must be a human's name, not an agent."}
    with _connect() as conn:
        a = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if a is None:
            return {"ok": False, "message": f"No approval {approval_id}."}
        if a["status"] != "pending":
            return {"ok": False, "message": f"Approval {approval_id} is '{a['status']}', not pending."}
        conn.execute(
            "UPDATE approvals SET status = ?, decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
            (decision, approver.strip(), _now(), note.strip() or None, approval_id))
        return {"ok": True, "approval_id": approval_id, "status": decision, "decided_by": approver.strip()}


@mcp.tool
def execute_approved_payment(approval_id: int) -> dict:
    """HUMAN ONLY. Pay an approved request in one transaction.

    Refuses unless the request is 'approved' by a human, and refuses if
    checking would go negative (the request is marked 'refused').
    On success: inserts payments (approved_by = the human), lowers
    cash_accounts.balance, and marks the invoice 'paid' or moves the
    lease's next_due forward one month. Purchase orders are paid to the
    vendor (stock arrives after lead_days; inventory is not changed today).
    Writes: payments, cash_accounts, invoices / leases, approvals.
    """
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        a = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if a is None:
            conn.rollback()
            return {"ok": False, "message": f"No approval {approval_id}."}
        if a["status"] != "approved" or not a["decided_by"]:
            conn.rollback()
            msg = ("A human must approve it first." if a["status"] == "pending"
                   else "Only 'approved' requests can be paid.")
            return {"ok": False, "message": f"Approval {approval_id} is '{a['status']}'. {msg}"}
        today = _today(conn)
        bal = _checking_balance(conn)
        if bal is None or a["amount"] > bal:
            conn.execute(
                "UPDATE approvals SET status = 'refused', decision_note = "
                "COALESCE(decision_note || ' | ', '') || 'Refused: not enough cash' WHERE id = ?",
                (approval_id,))
            conn.commit()
            return {"ok": False, "refused": True, "message": "Not enough cash. No negative balances.",
                    "amount": a["amount"], "checking_balance": bal}
        if a["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (a["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                conn.rollback()
                return {"ok": False, "message": f"Invoice {a['ref_id']} is not open."}
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (a["ref_id"],))
            effect = {"invoice_id": a["ref_id"], "invoice_status": "paid"}
        elif a["kind"] == "rent":
            lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (a["ref_id"],)).fetchone()
            new_due = _add_month(lease["next_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, a["ref_id"]))
            effect = {"lease_id": a["ref_id"], "old_next_due": lease["next_due"], "new_next_due": new_due}
        else:  # purchase_order
            if conn.execute("SELECT 1 FROM invoices WHERE vendor_id = ? AND status = 'open'",
                            (a["vendor_id"],)).fetchone():
                conn.rollback()
                return {"ok": False, "blocked": True, "message": "Vendor has an open invoice; it will not ship."}
            effect = {"vendor_id": a["vendor_id"], "sku": a["sku"], "size": a["size"], "qty": a["qty"]}
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?, ?, ?, 'checking', ?, ?)",
            (a["kind"], a["ref_id"], a["amount"], today, a["decided_by"]))
        new_bal = round(bal - a["amount"], 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = 'checking'", (new_bal, today))
        conn.execute("UPDATE approvals SET status = 'executed', payment_id = ? WHERE id = ?",
                     (cur.lastrowid, approval_id))
        conn.commit()
        return {"ok": True, "payment_id": cur.lastrowid, "kind": a["kind"], "amount": a["amount"],
                "approved_by": a["decided_by"], "paid_at": today,
                "checking_before": bal, "checking_after": new_bal, **effect}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


HUMAN_ONLY_TOOLS = {"record_human_decision", "execute_approved_payment"}


if __name__ == "__main__":
    _ensure_workflow_tables()
    mcp.run()
