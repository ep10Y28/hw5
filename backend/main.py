"""Campus Customs backend: FastAPI routes for the React dashboard.

Start (from the backend/ folder):
    uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs

Design
- All shop data goes through our MCP server (mcp_server/server.py), never
  straight SQL. The app keeps two MCP connections open:
    * the agent team's (each agent sees only its allowlisted tools), and
    * a "human desk" client, the only caller of the human-only tools
      record_human_decision and execute_approved_payment.
- Agents only PREPARE payments (pending approvals). The approve route is
  the only thing that moves cash, and only after a person approves.
- Agent runs take a minute or two, so POST /run starts a background task and
  returns its ticket_run_id at once. The dashboard polls /api/events and
  /api/runs/{id}. Only one agent run at a time (they share one database
  and one cash balance).
- Human approvals, rejections and resets are appended to
  output/audit_trail.json next to the agent steps.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# `uvicorn main:app` runs from backend/, so put the project root on the path
# and import the agent team as the `backend` package.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastmcp import Client  # noqa: E402
from fastmcp.client.transports import StdioTransport  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import audit  # noqa: E402
from backend.team import CampusTeam  # noqa: E402

ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"
SERVER_SCRIPT = ROOT / "mcp_server" / "server.py"
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}


class State:
    team: CampusTeam | None = None
    team_error: str | None = None
    desk: Client | None = None          # human-desk MCP client
    run_lock = asyncio.Lock()           # one agent run at a time
    runs: dict[str, dict[str, Any]] = {}
    tasks: set[asyncio.Task] = set()


S = State()


def _desk_client() -> Client:
    return Client(StdioTransport(command=sys.executable, args=[str(SERVER_SCRIPT)], cwd=str(ROOT)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    S.desk = _desk_client()
    await S.desk.__aenter__()
    try:
        S.team = CampusTeam()
        await S.team.__aenter__()
    except Exception as exc:  # e.g. PORTKEY_API_KEY missing: other routes still work
        S.team, S.team_error = None, f"{type(exc).__name__}: {exc}"
    yield
    for t in list(S.tasks):
        t.cancel()
    if S.team:
        await S.team.__aexit__(None, None, None)
    await S.desk.__aexit__(None, None, None)


app = FastAPI(title="Campus Customs Desk API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"], allow_headers=["*"],
)


async def mcp(tool: str, args: dict | None = None) -> dict:
    """Call one MCP tool on the human-desk connection and return its dict."""
    res = await S.desk.call_tool(tool, args or {}, raise_on_error=False)
    if res.is_error:
        raise HTTPException(500, f"MCP tool {tool} failed: {res.content[0].text if res.content else ''}")
    return res.structured_content or json.loads(res.content[0].text)


# ------------------------------------------------------------------ models

class ApproveBody(BaseModel):
    approver: str = Field(..., min_length=2, description="The person approving (not an agent name).")
    note: str = ""


class RejectBody(BaseModel):
    approver: str = Field(..., min_length=2)
    note: str = ""


# ------------------------------------------------------------------ routes

@app.get("/api/health")
async def health():
    return {"ok": True, "agents_ready": S.team is not None, "agents_error": S.team_error,
            "run_in_progress": S.run_lock.locked(), "model": "gpt-6-luna"}


@app.get("/api/tickets")
async def list_tickets():
    """Every ticket with its status and whether it is open or resolved."""
    data = await mcp("list_tickets")
    return {"today": data["today"], "tickets": [
        {"id": t["id"], "type": t["type"], "requester": t["requester"], "subject": t["subject"],
         "sku": t["sku"], "size": t["size"], "qty": t["qty"], "status": t["status"],
         "state": "open" if t["is_open"] else "resolved", "notes": t["notes"]}
        for t in data["tickets"]]}


@app.get("/api/tickets/{ticket_id}")
async def ticket_detail(ticket_id: int):
    """One ticket with its board posts (drafts, notes, decisions) and approvals."""
    data = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not data.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}")
    return data


async def _run_in_background(run_id: str, ticket_id: int) -> None:
    rec = S.runs[run_id]
    async with S.run_lock:
        rec["status"] = "running"
        try:
            outcome = await S.team.run_ticket(ticket_id, ticket_run_id=run_id)
            rec.update(status="done", outcome=outcome.model_dump())
        except Exception as exc:
            rec.update(status="error", error=f"{type(exc).__name__}: {exc}")


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int, wait: bool = False):
    """Run the agent team on one ticket. Returns a ticket_run_id right away
    (poll /api/runs/{id} and /api/events); ?wait=true blocks until done."""
    if S.team is None:
        raise HTTPException(503, f"Agent team not available: {S.team_error}")
    t = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not t.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}")
    if t["ticket"]["status"] == "resolved":
        raise HTTPException(409, f"Ticket {ticket_id} is already resolved.")
    if S.run_lock.locked():
        raise HTTPException(409, "Another agent run is in progress. Wait for it to finish.")
    run_id = uuid.uuid4().hex[:8]
    S.runs[run_id] = {"ticket_run_id": run_id, "ticket_id": ticket_id, "status": "queued",
                      "started": audit.now()}
    task = asyncio.create_task(_run_in_background(run_id, ticket_id))
    S.tasks.add(task)
    task.add_done_callback(S.tasks.discard)
    if wait:
        await task
    return S.runs[run_id]


@app.get("/api/runs")
async def list_runs():
    """Agent runs started since the server came up (newest first), and the active one."""
    runs = sorted(S.runs.values(), key=lambda r: r["started"], reverse=True)
    active = next((r for r in runs if r["status"] in ("queued", "running")), None)
    return {"active": active, "runs": runs}


@app.get("/api/runs/{run_id}")
async def run_status(run_id: str):
    """Status of one agent run: queued | running | done (with outcome) | error."""
    if run_id not in S.runs:
        raise HTTPException(404, "Unknown run id (runs are kept in memory until the server restarts).")
    return S.runs[run_id]


@app.get("/api/events")
async def events(since: int = Query(0, ge=0, description="Return entries after this index."),
                 limit: int = Query(100, ge=1, le=500),
                 ticket_id: int | None = None,
                 ticket_run_id: str | None = None):
    """Recent agent events from the audit trail: what each agent said and which
    tools it called (with results). Use next_since to poll for new ones."""
    data = _read_audit()
    out = []
    for i, e in enumerate(data):
        if i < since:
            continue
        if ticket_id is not None and e.get("ticket_id") != ticket_id:
            continue
        if ticket_run_id and e.get("ticket_run_id") != ticket_run_id:
            continue
        out.append({"index": i, **{k: e.get(k) for k in (
            "time", "ticket_id", "ticket_run_id", "agent", "event", "step", "chain", "delegated_to",
            "text", "tool_calls", "tool_results", "stop_reason", "tokens", "ticket_usage", "output")}})
    return {"total": len(data), "next_since": len(data), "events": out[-limit:]}


def _text_summary(text: str | None) -> str | None:
    """Older run_end entries only kept the report as cut-off JSON text."""
    import re
    if not text or not text.lstrip().startswith("{"):
        return text
    m = re.search(r'"(?:summary|decision)":\s*"((?:[^"\\]|\\.)*)', text)
    if not m:
        return text
    try:
        return json.loads(f'"{m.group(1).rstrip(chr(92))}"')
    except ValueError:
        return m.group(1)


def _read_audit() -> list[dict]:
    path = audit.AUDIT_PATH
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() and path.stat().st_size else []


@app.get("/api/tickets/{ticket_id}/summary")
async def ticket_summary(ticket_id: int, ticket_run_id: str | None = None):
    """Short per-agent recap of the latest (or given) run on a ticket: what each
    agent concluded, which tools it used, who it handed work to, ids it created."""
    entries = [e for e in _read_audit() if e.get("ticket_id") == ticket_id and e.get("ticket_run_id")]
    if not entries:
        return {"ticket_id": ticket_id, "ticket_run_id": None, "agents": [], "outcome": None}
    run_id = ticket_run_id or entries[-1]["ticket_run_id"]
    entries = [e for e in entries if e["ticket_run_id"] == run_id]
    order, agents = [], {}
    for e in entries:
        name = e.get("agent")
        if name not in agents:
            order.append(name)
            agents[name] = {"agent": name, "summary": None, "tools_used": [], "delegated_to": [],
                            "approval_ids": [], "board_ids": [], "blocked_actions": 0,
                            "steps": 0, "tokens": 0, "status": "running"}
        a = agents[name]
        if e["event"] == "model_step":
            a["steps"] += 1
            a["tokens"] += sum((e.get("tokens") or {}).values()) if e.get("tokens") else 0
            for c in e.get("tool_calls") or []:
                if c["tool"] not in ("final_result", "delegate") and c["tool"] not in a["tools_used"]:
                    a["tools_used"].append(c["tool"])
        elif e["event"] == "delegation" and e.get("delegated_to"):
            a["delegated_to"].append(e["delegated_to"])
        elif e["event"] == "guardrail":
            a["blocked_actions"] += 1
        elif e["event"] == "run_end":
            out = e.get("output") or {}
            a["status"] = "done"
            a["summary"] = out.get("summary") or out.get("decision") or _text_summary(e.get("text"))
            a["approval_ids"] = out.get("approval_ids", [])
            a["board_ids"] = out.get("board_ids", [])
            if name == "boss":
                a["outcome"] = out
        elif e["event"] == "error":
            a["status"] = "error"
            a["summary"] = e.get("text")
    boss = agents.get("boss", {})
    return {"ticket_id": ticket_id, "ticket_run_id": run_id,
            "started": entries[0]["time"], "finished": entries[-1]["time"],
            "outcome": boss.get("outcome"), "agents": [agents[n] for n in order]}


@app.get("/api/approvals")
async def approvals(status: str = "pending"):
    """Payments and purchase orders the agents prepared (default: pending),
    with the payee and a short memo filled in from the database for the cheque."""
    data = await mcp("list_approvals", {"status": status})
    vendors = {v["id"]: v for v in (await mcp("list_vendors"))["vendors"]}
    leases: dict[int, dict] = {}
    for a in data["approvals"]:
        if a["kind"] == "rent":
            if a["ref_id"] not in leases:
                leases[a["ref_id"]] = await mcp("get_lease_rent_due", {"lease_id": a["ref_id"]})
            l = leases[a["ref_id"]]
            a["payee"] = l.get("landlord")
            a["memo"] = f"Rent · {l.get('space_name')} · due {l.get('next_due')}"
        elif a["kind"] == "invoice":
            a["payee"] = vendors.get(a["vendor_id"], {}).get("name")
            a["memo"] = f"Invoice {a['ref_id']}"
        else:
            a["payee"] = vendors.get(a["vendor_id"], {}).get("name")
            a["memo"] = f"PO · {a['qty']} × {a['sku']} {a['size']}"
    return data


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: ApproveBody):
    """A human approves a pending payment or purchase order, and it is paid.
    This is the ONLY route that changes cash. It refuses if cash would go negative."""
    approver = body.approver.strip()
    if approver.lower() in AGENT_NAMES:
        raise HTTPException(400, "approver must be a person, not an agent.")
    decision = await mcp("record_human_decision", {"approval_id": approval_id, "decision": "approved",
                                                   "approver": approver, "note": body.note})
    if not decision.get("ok"):
        raise HTTPException(409, decision.get("message"))
    payment = await mcp("execute_approved_payment", {"approval_id": approval_id})
    audit.append({"agent": "human", "event": "human_decision", "approval_id": approval_id,
                  "text": f"{approver} approved #{approval_id}", "stop_reason": "approved",
                  "tool_calls": [{"tool": "execute_approved_payment", "args": audit.short({"approval_id": approval_id})}],
                  "tool_results": [{"tool": "execute_approved_payment", "result": audit.short(payment)}]})
    cash = await mcp("get_cash_position")
    return {"approval": decision, "payment": payment, "checking_balance": cash["checking_balance"]}


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: RejectBody):
    """A human rejects a pending request. No money moves."""
    decision = await mcp("record_human_decision", {"approval_id": approval_id, "decision": "rejected",
                                                   "approver": body.approver.strip(), "note": body.note})
    if not decision.get("ok"):
        raise HTTPException(409, decision.get("message"))
    audit.append({"agent": "human", "event": "human_decision", "approval_id": approval_id,
                  "text": f"{body.approver.strip()} rejected #{approval_id}. {body.note}".strip(),
                  "stop_reason": "rejected"})
    return decision


@app.get("/api/cash")
async def cash():
    """Current checking balance from cash_accounts, plus money reserved by
    pending approvals and open obligations."""
    c = await mcp("get_cash_position")
    return {"account": "checking", "balance": c["checking_balance"], "as_of": c["today"],
            "reserved_by_pending_approvals": c["reserved_in_pending_or_approved_requests"],
            "available_after_reserved": c["available_after_reserved"],
            "open_obligations_total": c["open_obligations_total"]}


@app.post("/api/reset")
async def reset():
    """Copy data/campus_customs.db over the working copy (fresh run).
    Refuses while an agent run is in progress. The audit trail is NOT wiped."""
    if S.run_lock.locked():
        raise HTTPException(409, "An agent run is in progress. Reset after it finishes.")
    async with S.run_lock:
        shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    audit.append({"agent": "human", "event": "reset",
                  "text": f"Working DB reset from {ORIGINAL_DB.name}", "stop_reason": "reset"})
    cash_now = await mcp("get_cash_position")
    return {"ok": True, "message": "Working database restored to original values.",
            "checking_balance": cash_now["checking_balance"]}
