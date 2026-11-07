# AI Prompts Log — MGT 409 HW5: Campus Customs Multi-Agent Operations

This file is the log of what I typed to my vibe coder (Claude). There is one section per problem (11 total). Each section has the problem number and title, at least one prompt I typed in my own words, and a follow-up prompt if one was needed (with one sentence on what was lacking after the first).

---

## Problem 1: Vibe Coder Prompts

**Prompt:**

> Alright, Problem 1: Vibe coder prompts
>
> Create AI_prompts.md and this will be the vibe coder.  We will put one section for each problem and each section must include:
>
> -the problem number and title
> -at least one prompt i typed in my own words
> -one follow up prompt if needed (and one sentence on what was lacking after the first)

**Follow-up prompt:** None needed.

---

## Problem 2: Study the Campus Customs Database

**Prompt:**

> Problem 2: study the campus customs database
>
> open data/campus_customs.db and look through every table and fields. copy the original file to data/campus_customs_new.db - later problems update that working copy.
>
> study the three open tickets so I see how they link to other tables.
>
> start output/harness.md. for each table, list the fields and one short line on why that table matters for the agents based on what you know.
>
> we will keep growing this harness file in later problems.

**Follow-up prompt:** None needed.

---

## Problem 3: Build the MCP Server

**Prompt:**

> problem 3 - build the mcp server
>
> write an mcp server in mcp_server/ using FastMCP. it will talk to data/campus_customs_new.db. we do not need to connect or run it in this problem.
>
> every agent in this homework uses the tools in this MCP server. you will add more tools to it later. for now, write three tools we know we will need for the tickets in the database. keep the names clear. never invent any data and only use information in the database.
>
> in output/harness.md, list each of your three MCP tools. for every tool, include:
>
> -which table it reads, which ticket it helps unlock (101, 102, or 103), and one sentence on why that tool is the right one for that ticket.
>
> vague lines like "reads inventory" score low - tie the tool to the ticket.
>
> also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses, and the three tools it has

**Follow-up prompt:** None needed.

---

## Problem 4: Add the MCP Server to the Vibe Coder and Test Each Tool

**Prompt:**

> problem 4 - add the MCP server to viber coder and test each tool
>
> Add our MCP server to this project so that you can call the tools. save the connection JSON text in .mcp.json at the project root (or however we save local MDP server lists).
>
> once you're connected, test each of your three MCP tools. save the evidence in output/mcp_smoke.json. for every tool, include:
>
> -the prompt I asked you
> -the tool name
> -the tool output (must match values in data/campus_customs_new.db)

**Follow-up prompt:** None needed.

---

## Problem 5: Build the Agent Team and Grow the MCP Tools

**Prompt:**

> problem 5 - build the agent team and grow the MCP tools
>
> build the agentic team for Campus Customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity.
>
> put the agent prompts in backend/prompts/ - one file per agent. put data types in backend/models.py, and the agent files under backend/ (our layout can vary as long as the five roles are clear). use our PORTKEY_API_KEY and only gpt-6-luna for every agent.
>
> Let's prompt each agent with the shop rules that agent would hypothetically need.  More detailed prompts that cover all aspects of an agent's work and scope will score higher for us than a short generic prompt.
>
> add any tools the agents need to our MCP server so they can work on the open tickets. shop facts come from the MCP server over data/campus_customs_new.db - do not invent a second shop tools layer that bypasses MCP.
>
> wire the agents so they append to output/audit_trail.json as they run. For each agent-loop step, record enough to audit later. Append to this file - do not wipe each run.
>
> In output/harness.md, list each agent and each MCP tool (including ones we add in this problem) along with  which table the tool uses.  Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check.
>
> Update mcp_server/README.md so the tool list matches what we have now.

**Follow-up prompt:**

> *(Pasted the terminal output from the first live run of `python -m backend.run_tickets --reset --ticket 101`.)*

What was lacking: the first version called gpt-6-luna through Portkey's chat-completions endpoint, which rejects tool calls while reasoning is on (400: "use /v1/responses or set reasoning_effort to 'none'"), so we switched the agents to the Responses API.

---

## Problem 6: Plan the Three Tickets

**Prompt:**

> problem 6 - plan the three tickets
>
> before we wire the backend, let's write down what we expect the team to do on each open ticket. build output/desk_tickets.html - a page we can double-click with one tab per ticket (101, 102, and 103). Also add empty Cash and Reflection tabs for later problems (leave them blank or with a short "coming later" note for now).
>
> On each ticket tab, fill an Expected section only (leave room for an Actual section we will fill after we run the agents).
>
> For each ticket's Expected section, write in our own words:
>
> -who the Boss should call first and why
> -all the agent delegations we expect - not "Boss calls everyone"
> -which MCP tools we expect that run to use
>
> Plans that send every specialist on every ticket score very low. We will compare this plan to what actually happens when your agents resolve the three tickets.

**Follow-up prompt:** None needed.

---

## Problem 7: Backend Routes

**Prompt:**

> Problem 7 - backend routes
>
> Our React frontend dashboard (the next problem) needs a backend it can call. In backend/main.py, use FastAPI and add routes that do the following:
>
> -return the three tickets and whether each is open or resolved
> -take a ticket ID and run our agent team on that ticket
> -return recent agent events - what each agent said and which tools they used - so the board can refresh
> -approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash)
> -return the current checking balance from cash_accounts
> -reset the database to the original values when we want to try a fresh run
>
> From the backend/ folder, start the server with:
>
> uvicorn main:app --reload --port 8000
>
> This turns on our backend at http://localhost:8000 so the frontend dashboard can call those routes.
>
> In output/harness.md, list each route in one line (what URL/what it does).

**Follow-up prompt:** None needed.

---

## Problem 8: Agent Dashboard

**Prompt:**

> problem 8 - agent dashboard
>
> build the frontend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes we built in Problem 7. At minimum, the board should:
>
> -list all 3 tickets

**Follow-up prompt:**

> here is the full list:
>
> -list all 3 tickets
> -let me pick one ticket and start the agent team on it
> -show each agent and what they are saying/doing while the ticket runs
> -mark a ticket resolved when the run finishes
> -show a short summary of what each agent did on that ticket
> -let a human approve a pay or purchase when asked
> -show the checking balance (it should drop after an approved pay)
>
> make the dashboard look good. be creative with the layout and feel - this is a real desk people would want to sit at - so put thought into how it looks.
>
> tell the front end to talk to my backend at http://localhost:8000. On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes.
>
> Start the board with:
>
> npm run dev
>
> This opens the React desk in our browser so we can pick tickets and watch agents.
>
> Write output/design.md with what we chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why - including the creative choices that make it feel special and something humans would actually enjoy using.

What was lacking: my first message got cut off after the first bullet, so the vibe coder only had "list all 3 tickets" and asked for the rest of the requirements before building.

---

## Problem 9: Resolve the Tickets

**Prompt:**

> problem 9 - resolve the tickets
>
> before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so we start clean.  Note the starting checking balance.  Then run all three tickets on the board (101, 102, and 103) until each is resolved.
>
> Open output/desk_tickets.html from Problem 6. On each ticket tab, fill the Actual section from this run: which agents worked, what they delegated, and which tools they used.  Keep your Expected section so you can compare the two.
>
> On the Cash tab of the same output/desk_tickets.html, itemize the money.
>
> -starting checking balance (after the reset)
> -for each ticket: how cash changed when that ticket resolved, and why (which pay/purchase, dollar amount)
> -ending checking balance - it must match cash_accounts in the working database
>
> wrong cash math loses points even if the board shows every ticket resolves. Also save:
>
> -output/resolved_tickets.jason - for each ticket: ID, final status, short outcome, what each agent contributed, and any human approvals
> -output/resolved_board.html - a page we can double-click with a screenshot of our React board for each resolved ticket (101, 102, 103).
>
> Append real runs to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools. the five agents, API routes, the dashboard, and safety rules.

**Follow-up prompt:** None needed.

---

## Problem 10: Reflection

**Prompt:**

> Problem 10 - Reflection
>
> open output/desk_tickets.html and fill the Reflection tab. Answer in our own vibe, and be detailed and thorough.
>
> -how would we evaluate the performance of the agents on each ticket and why?
> -for each ticket, how did Actual compare to the Expected plan we wrote together earlier?
> -what would have been simpler as one agent with tools - and why?
> -describe 3 new problems Campus Customs might face that this agent team could solve with the tools we built
> -describe 3 new problems Campus Customs might face that this agent team could not solve with the tools we built, and explain the tools and agents we would need to solve them.
>
> Tie every answer you write to this app and the three tickets we ran.  Use the ticket tabs and Cash tab on the same page as our evidence.
>
> Generic AI essays without Campus Customs details will score low.
>
> Go.

**Follow-up prompt:** None needed.

---

## Problem 11: Submit to GitHub

**Prompt:**

> Problem 11 - submit to github
>
> Push our code to a public GitHub repository so graders can clone it.  Submit the repo URL to canvas (I will do this), and also put it in output/github_url.txt.
>
> Do not push our real .env to the GitHub repo.  Do include both database files under data/ (the original and your working copy) so graders can run our app easily.
>
> Expected file layout: screenshot attached.
>
> README should explain: copy original DB to the working copy when we need a clean run, start MCP server, start FastAPI backend, start the React board, reset the DB before a full three-ticket run.
>
> Go.

**Follow-up prompt:** None needed.

---
