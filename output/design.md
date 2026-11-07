# Campus Customs Operations Desk: Design Notes

**Concept: a real shop desk at closing time.** Paper tickets on a spike, the team at their desks, a till you can watch, and a stack of cheques waiting for your signature. Every visual metaphor maps to something true about the system. Agents *prepare* work, and a person *signs* it. We wanted the screen to make that difference something you can feel, not just read in a README.

Built with React + Vite + TypeScript in `frontend/`. It talks to the FastAPI backend at `http://localhost:8000` (`src/api.ts`, override with `VITE_API_URL`). Start it with `npm install` then `npm run dev`, which opens http://localhost:5173. The backend allows that origin through CORS.

---

## Layout: three columns, read left to right like a workflow

| Left: **Ticket spike** | Center: **The floor** | Right: **Needs your signature** |
|---|---|---|
| What came in | Who is working on it, and what they're doing | What only a person can do |

- **Sticky header (the counter).** The brand, the shop date (`desk.date_today`, so nobody confuses the shop's "today" with the real one), a live status pill ("Floor is quiet" / "Team working on #102"), the **cash till**, and Reset. It stays pinned so the till is always in view. You see cash move the moment you sign.
- **Left: ticket spike.** Each ticket is a paper stub with a perforated edge and a big serif ticket number, like a deli or repair ticket. Click one to bring it to the center. The selected stub slides out slightly, and only it shows the **"Hand to the team →"** button, so you can't fire off the wrong ticket by accident.
- **Center: the floor.** Five agent seats across the top, then two tabs: **Live wire** (the transcript while the run happens) and **Recap** (the summary when it's done). After a run, the desk switches to Recap on its own.
- **Right: signature tray.** Pending payments and purchase orders appear as **cheques**. Signed ones drop into a "Signed today" pile below.

Why this order: it matches how a manager thinks. What's on my plate → what is my team doing about it → what needs my signature. The things that need a human are always on the same side of the screen and never mixed in with agent chatter.

---

## How agents read differently

Each agent has its own **colour, monogram and voice**, used the same way everywhere (seats, transcript, recap cards), so after a minute you know who's talking without reading the name.

| Agent | Colour | Monogram | Voice (type treatment) | Why |
|---|---|---|---|---|
| Boss | Yale navy (the desk's own colour), solid avatar with a brass ring | **B** | Serif, slightly larger | Boss makes the call. Its lines should read like decisions, not chatter |
| Inventory | Teal | **In** | Clean sans | Counts and sizes: crisp and factual |
| Accounting | Ledger green | **Ac** | Tabular (aligned) numerals | Money lines up the way it does in a ledger |
| Facilities | Terracotta / brick | **Fa** | Sans | The building: warm, earthy |
| Customer Service | Plum | **CS** | Serif *italic* | It writes to people, so it reads like a letter |

**The seats are alive.** Each seat shows its current state and its latest action in plain English:
- **idle:** greyed out, "at their desk" / "on standby"
- **speaking:** the active agent's avatar breathes, with a soft halo and typing dots ("counted stock •••")
- **waiting:** "asked Accounting · waiting" when it has handed off work and is waiting on the reply
- **done:** a green check, "reported back"

Agents that aren't needed stay at their desks. When Facilities sits idle through ticket 101, that *shows* that Boss didn't send every specialist to every ticket.

**The live wire** is a transcript, not a log dump:
- **Messages:** bubbles with the agent's colour rule and voice.
- **Tool calls:** dashed "receipt" chips that pair a friendly verb with the real tool name and its key arguments ("counted stock · `check_stock_by_size` sku=CC-TEE-WHITE size=S"). Managers get the verb, and auditors get the exact tool.
- **Tool results:** indented mono lines underneath, the machine's answer.
- **Hand-offs:** striped cards ("Boss hands off to Accounting") that quote the actual task text, so you can judge whether Boss asked a good question.
- **Guardrail blocks:** amber notes. When a rule stops an agent, you see it.
- **Reports:** tinted cards with a REPORT / FINAL CALL tag.
- **Auto-scroll:** the transcript scrolls inside its own panel, never the whole page, so the till and tray stay put.

---

## How resolved tickets show up

- When Boss's run finishes, the backend marks the ticket **resolved**. The stub gets a green **RESOLVED rubber stamp** that thunks on with a little overshoot, and the stub goes slightly faded, like a ticket that's been dealt with. The ticket header pill turns green, and the rail counter updates ("2 open · 1 resolved").
- A toast confirms it: "Ticket 101 resolved. The team's recap is ready."
- **Recap tab:**
  - **Boss's call** comes first, in a dark navy card set like a pull quote, followed by **"Left for a person"**, Boss's `needs_human` list. Resolved means the team is done, not that everything is done, and this keeps that honest.
  - **One card per agent:** what it concluded, steps and tools used, who it handed to, and what it created (approval #, board #). Agents that weren't called don't get a card.
  - **Customer drafts** appear as a lined letter with a purple **DRAFT · NOT SENT** stamp, a reminder that nothing went out.

## How cash shows up

- **The till** in the header shows the checking balance from `cash_accounts` in large serif numerals, with two smaller lines underneath: **"Promised to pending approvals"** and **"Free"**. "Free" turns amber when it drops under $300. In this shop, rent plus invoice 501 leave just $160, and the desk should make you feel that squeeze before you sign.
- When you approve a payment, the number **counts down** to the new balance, a **−$840** chip flashes red and fades, the till glows briefly, and a tiny **sparkline** of today's balance steps down. It's the "drop after an approved pay" the assignment asks for, made visible.
- **Cheques** in the right tray are drawn like real cheques: a security-pattern green background, "Pay to the order of **Bulldog Print Co**", the amount in a box, a memo (invoice #, or rent · space · due date), and "prepared by Accounting" in the agent's colour.
  - You type your name once in **Signing as**. It's rendered in a handwriting font and saved in this browser.
  - Then **Sign & pay** or **Void**. A signed cheque gets a **PAID** stamp and your signature. A voided or refused one gets a red stamp.
  - The buttons stay disabled until there's a name. Paying should take a deliberate act by an identified person, which matches the backend rule that agents can't approve.

---

## The small creative choices that make it feel like a place

- **Paper, ink and brass:** an ivory paper background with a faint dotted texture, navy ink, and brass accents (the header rule, the selected ticket, the hand-off arrow). It's warm and calm, a desk you could sit at for an hour, not a neon ops console.
- **Serif for what people read and sign** (titles, money, cheques, Boss's call). **Sans** for working text. **Mono** for machine facts. The type tells you who's speaking: a person, an agent, or the database.
- **Physical metaphors map to real rules:** stubs = tickets, rubber stamps = status changes, cheques = approvals, the till = `cash_accounts`, the letter with DRAFT · NOT SENT = board drafts. Every metaphor is honest.
- **Motion with a purpose only:** breathing avatars while an agent thinks, a stamp "thunk", the till counting down. Nothing animates for decoration. With "reduce motion" turned on in the OS, all animation switches off.
- **Safety by design:** one run at a time (the Run button disables during a run), Reset needs two clicks ("Click again to reset") and is disabled during a run, and the signature is required before paying.
- **Friendly failure:** if the backend is down, a banner says exactly which command to run. If the agents can't load (for example, a missing Portkey key), the banner says why while the rest of the desk keeps working.
- **Footer promise:** "Agents prepare · people sign · every step is logged to output/audit_trail.json." That's the whole system in one line.

## How it maps to the requirements

| Requirement | Where |
|---|---|
| List all 3 tickets | Ticket spike (`GET /api/tickets`) |
| Pick a ticket and start the team | Select a stub → **Hand to the team →** (`POST /api/tickets/{id}/run`) |
| Show each agent and what it says/does during the run | Agent seats + Live wire, polled every 1.2s (`GET /api/events?since=…&ticket_run_id=…`, `GET /api/runs/{id}`) |
| Mark resolved when the run finishes | Backend resolves on finish. RESOLVED stamp + green pill + toast |
| Short summary of what each agent did | Recap tab (`GET /api/tickets/{id}/summary`) |
| Human approves a pay or purchase | Cheques → **Sign & pay** (`POST /api/approvals/{id}/approve`) |
| Checking balance that drops after an approved pay | The till (`GET /api/cash`) with a count-down, −$ chip and sparkline |
