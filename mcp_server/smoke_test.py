"""Smoke test: connect to the Campus Customs MCP server exactly as .mcp.json
describes (stdio subprocess), call each tool over MCP, cross-check every
value against data/campus_customs_new.db with direct SQL, and write the
evidence to output/mcp_smoke.json.

Run from the project root:  python mcp_server/smoke_test.py
"""
import asyncio, json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
CONFIG = json.loads((ROOT / ".mcp.json").read_text())
SERVER = "campus-customs"

STUDENT_PROMPT = (
    "problem 4 - add the MCP server to viber coder and test each tool ... "
    "once you're connected, test each of your three MCP tools."
)

TESTS = [
    {
        "ticket": 103,
        "prompt": "Using our MCP server, how many size M navy hoodies (CC-HOOD-NAVY) "
                  "do we have, and how short are we for the Yale AI Club's 20?",
        "tool": "check_stock_by_size",
        "args": {"sku": "CC-HOOD-NAVY", "size": "M", "qty_needed": 20},
    },
    {
        "ticket": 101,
        "prompt": "Using our MCP server, will Bulldog Print Co (vendor 1) ship the "
                  "size S tee reprint, or is an open invoice blocking it?",
        "tool": "get_vendor_invoice_status",
        "args": {"vendor_id": 1},
    },
    {
        "ticket": 102,
        "prompt": "Using our MCP server, how much rent is due on lease 1, when, "
                  "and does checking cover it?",
        "tool": "get_lease_rent_due",
        "args": {"lease_id": 1},
    },
]


def db_truth(tool, args):
    """Pull the same facts straight from SQLite to prove the tool didn't invent anything."""
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    today = c.execute("SELECT date_today FROM desk").fetchone()[0]
    if tool == "check_stock_by_size":
        r = c.execute("SELECT * FROM inventory WHERE sku=? AND size=?",
                      (args["sku"], args["size"])).fetchone()
        return {"sql": "SELECT qty FROM inventory WHERE sku=? AND size=?",
                "expected": {"qty_on_hand": r["qty"], "name": r["name"],
                             "shortfall": max(args["qty_needed"] - r["qty"], 0)}}
    if tool == "get_vendor_invoice_status":
        v = c.execute("SELECT * FROM vendors WHERE id=?", (args["vendor_id"],)).fetchone()
        inv = [dict(i) for i in c.execute(
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id=? AND status='open'",
            (args["vendor_id"],))]
        return {"sql": "SELECT * FROM vendors WHERE id=?; SELECT * FROM invoices WHERE vendor_id=? AND status='open'",
                "expected": {"vendor_name": v["name"], "lead_days": v["lead_days"],
                             "open_invoice_ids": [i["id"] for i in inv],
                             "open_balance": sum(i["amount"] for i in inv),
                             "will_ship": len(inv) == 0, "today": today}}
    if tool == "get_lease_rent_due":
        l = c.execute("SELECT * FROM leases WHERE id=?", (args["lease_id"],)).fetchone()
        bal = c.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
        return {"sql": "SELECT * FROM leases WHERE id=?; SELECT balance FROM cash_accounts WHERE name='checking'",
                "expected": {"monthly_rent": l["monthly_rent"], "next_due": l["next_due"],
                             "checking_balance": bal, "today": today}}


def compare(tool, out, exp):
    if tool == "get_vendor_invoice_status":
        got = dict(out, open_invoice_ids=[i["invoice_id"] for i in out["open_invoices"]])
    else:
        got = out
    mism = {k: {"tool": got.get(k), "db": v} for k, v in exp.items() if got.get(k) != v}
    return not mism, mism


async def main():
    cfg = {"mcpServers": {SERVER: dict(CONFIG["mcpServers"][SERVER])}}
    # Launch with this interpreter (it has fastmcp); args/cwd are exactly as in .mcp.json.
    cfg["mcpServers"][SERVER]["command"] = sys.executable
    cfg["mcpServers"][SERVER]["cwd"] = str(ROOT)
    results = []
    async with Client(cfg) as client:
        tools = [t.name for t in await client.list_tools()]
        for t in TESTS:
            res = await client.call_tool(t["tool"], t["args"])
            out = res.structured_content or json.loads(res.content[0].text)
            truth = db_truth(t["tool"], t["args"])
            ok, mism = compare(t["tool"], out, truth["expected"])
            results.append({
                "ticket": t["ticket"],
                "prompt": t["prompt"],
                "tool": t["tool"],
                "arguments": t["args"],
                "tool_output": out,
                "db_check": {"query": truth["sql"], "expected_from_db": truth["expected"],
                             "matches_db": ok, "mismatches": mism},
            })
    evidence = {
        "student_prompt": STUDENT_PROMPT,
        "connection": {"config_file": ".mcp.json", "server": SERVER,
                       "transport": "stdio", "config": CONFIG["mcpServers"][SERVER]},
        "database": "data/campus_customs_new.db",
        "tools_listed_by_server": tools,
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "all_match_db": all(r["db_check"]["matches_db"] for r in results),
        "tests": results,
    }
    out_path = ROOT / "output" / "mcp_smoke.json"
    out_path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"tools": tools, "all_match_db": evidence["all_match_db"]}))

asyncio.run(main())
