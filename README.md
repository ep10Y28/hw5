# Campus Customs: Multi-Agent Operations (MGT 409 · HW5)

An agent team runs the Campus Customs ticket board. Five PydanticAI agents (**Boss, Inventory, Accounting, Facilities, Customer Service**) work open tickets using an **MCP server** over the shop's SQLite database. A **FastAPI backend** runs the team and exposes routes, and a **React desk** lets a person watch the agents and approve payments. Every agent uses **gpt-6-luna via Portkey**, and nothing else.

> Agents only *prepare* payments. Money moves only when a person signs on the dashboard, and the pay tool refuses to take checking below zero.

```
hw5/
├── AI_prompts.md            what we typed to the vibe coder, one section per problem
├── requirements.txt         Python deps (fastmcp, pydantic-ai, fastapi, uvicorn, …)
├── .env.example             copy to .env and add PORTKEY_API_KEY (the real .env is not in git)
├── .mcp.json                registers the MCP server for Claude Code
├── data/
│   ├── campus_customs.db        ORIGINAL shop database (never modified)
│   └── campus_customs_new.db    WORKING copy the agents read and write
├── mcp_server/   server.py (17 MCP tools), README.md, smoke_test.py
├── backend/      main.py (FastAPI), models.py, team.py (agent loop), agents/, prompts/ (one per agent), …
├── frontend/     React + Vite + TypeScript desk
└── output/       harness.md, mcp_smoke.json, desk_tickets.html, design.md,
                  resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt
```

## Setup (once)

Requires Python 3.11+ and Node 18+.

```bash
git clone https://github.com/ep10Y28/hw5.git && cd hw5
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then put your PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

## 1. Copy the original DB to the working copy (clean run)

The agents only touch `data/campus_customs_new.db`. To start from the original shop state (checking $3,400, tickets 101–103 open), copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The committed working copy holds the end state of our graded run (all three tickets resolved, checking $160), so copy first if you want a fresh start. The **Reset shop** button on the desk does the same copy (see step 5).

## 2. Start the MCP server

The MCP server (`mcp_server/server.py`, FastMCP, stdio) is the only layer that touches the database. You don't need a separate terminal for it:
- **The FastAPI backend starts it automatically** as a child process when the backend boots (step 3).
- **Claude Code** starts it from `.mcp.json` when you open this folder.

To run it by hand or check it:

```bash
python mcp_server/server.py          # starts the server on stdio (Ctrl+C to stop)
python mcp_server/smoke_test.py      # connects like a client, calls the tools, checks values vs the DB
```

## 3. Start the FastAPI backend

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --reload --port 8000
```

The backend runs at http://localhost:8000 (interactive docs at http://localhost:8000/docs). It loads `PORTKEY_API_KEY` from `.env` and allows the desk's origin, `http://localhost:5173`. Its routes:
- `GET /api/tickets`, `POST /api/tickets/{id}/run`
- `GET /api/events`, `GET /api/tickets/{id}/summary`
- `GET /api/approvals`, `POST /api/approvals/{id}/approve` (the only route that moves cash)
- `GET /api/cash`, `POST /api/reset`

## 4. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

This opens the desk at http://localhost:5173.
- **Pick a ticket**, then **Hand to the team →**, and watch the agents on the Live wire.
- The **Recap** opens when the ticket is resolved.
- **Sign & pay** any cheques in "Needs your signature". The till drops after each signed payment.

## 5. Reset the DB before a full three-ticket run

Always start a full run from the original books:
1. Click **↺ Reset shop** twice on the desk. This is the same as `POST /api/reset`, or `cp data/campus_customs.db data/campus_customs_new.db` while the backend is stopped.
2. Confirm the till shows **$3,400.00**.
3. Run **101 → 102 → 103** in order, signing or voiding each cheque before starting the next ticket.

Our run: invoice 501 ($840) and rent ($2,400) were signed, and the $264 hoodie restock didn't fit, so checking ended at **$160.00** (see `output/desk_tickets.html` → Cash).

From the command line instead:

```bash
python -m backend.run_tickets --reset --all
```

This queues approvals but can't sign them. Use the desk to approve.

## Where to look

| File | What it shows |
|---|---|
| `output/harness.md` | Tables, all 17 MCP tools, the five agents, API routes, the dashboard, safety and token limits, run results |
| `output/desk_tickets.html` | Per ticket: Expected plan vs. Actual run, plus the Cash ledger and the Reflection |
| `output/resolved_tickets.json` | Each ticket's final status, outcome, agent contributions and human approvals |
| `output/resolved_board.html` | Screenshots of the React board for each resolved ticket |
| `output/audit_trail.json` | Append-only log of every agent-loop step, delegation, guardrail, approval and reset |
| `output/design.md` | Why the desk looks and behaves the way it does |
| `output/mcp_smoke.json` | Evidence that each MCP tool's output matches the database |
