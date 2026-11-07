"""Run the agent team on tickets from the command line.

From the hw5 folder:
    python -m backend.run_tickets --ticket 101
    python -m backend.run_tickets --all
    python -m backend.run_tickets --reset --all     # restore the original DB first
    python -m backend.run_tickets --ask accounting "What is our cash position?"

Every run appends to output/audit_trail.json. Payments stay 'pending' until a
human approves them (dashboard, later problem).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sqlite3

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # keep terminal output readable

from .audit import ROOT
from .team import CampusTeam

ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"


def reset_db() -> None:
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    print(f"Reset {WORKING_DB.name} from {ORIGINAL_DB.name}")


def open_ticket_ids() -> list[int]:
    with sqlite3.connect(WORKING_DB) as c:
        return [r[0] for r in c.execute("SELECT id FROM tickets WHERE status != 'resolved' ORDER BY id")]


async def main(args) -> None:
    if args.reset:
        reset_db()
    async with CampusTeam() as team:
        if args.ask:
            agent, question = args.ask
            out = await team.ask(agent, question, ticket_id=args.ticket)
            print(json.dumps(out.model_dump(), indent=2))
            return
        ids = open_ticket_ids() if args.all else [args.ticket]
        for tid in ids:
            print(f"\n=== Ticket {tid} ===")
            outcome = await team.run_ticket(tid)
            print(json.dumps(outcome.model_dump(), indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    p.add_argument("--ticket", type=int)
    p.add_argument("--all", action="store_true", help="work every open ticket in id order")
    p.add_argument("--reset", action="store_true", help="copy campus_customs.db over the working copy first")
    p.add_argument("--ask", nargs=2, metavar=("AGENT", "QUESTION"))
    a = p.parse_args()
    if not (a.ticket or a.all or a.ask):
        p.error("give --ticket N, --all, or --ask AGENT QUESTION")
    asyncio.run(main(a))
