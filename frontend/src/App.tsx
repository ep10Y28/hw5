import { useCallback, useEffect, useRef, useState } from "react";
import { api, API_BASE } from "./api";
import { TICKET_TYPE } from "./agents";
import { AgentFloor } from "./components/AgentFloor";
import { CashTill } from "./components/CashTill";
import { LiveWire } from "./components/LiveWire";
import { Recap } from "./components/Recap";
import { SignatureTray } from "./components/SignatureTray";
import { TicketRail } from "./components/TicketRail";
import { loadPref, savePref, useInterval } from "./hooks";
import type { AgentEvent, Approval, Cash, Run, Ticket, TicketDetail, TicketSummary } from "./types";

type Toast = { id: number; text: string; tone: "ok" | "warn" | "err" };

function prettyDate(iso: string) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [today, setToday] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [wireRunId, setWireRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const cursor = useRef(0);
  const [summary, setSummary] = useState<TicketSummary | null>(null);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [cashHistory, setCashHistory] = useState<number[]>([]);
  const [view, setView] = useState<"wire" | "recap">("wire");
  const [signer, setSignerState] = useState(loadPref("cc.signer", ""));
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [offline, setOffline] = useState<string | null>(null);
  const [agentsReady, setAgentsReady] = useState(true);
  const [armReset, setArmReset] = useState(false);

  const running = activeRun != null && (activeRun.status === "running" || activeRun.status === "queued");

  const toast = useCallback((text: string, tone: Toast["tone"] = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5200);
  }, []);
  const setSigner = (s: string) => { setSignerState(s); savePref("cc.signer", s); };

  // ---------------------------------------------------------------- loaders
  const loadTickets = useCallback(async () => {
    const d = await api.tickets();
    setTickets(d.tickets); setToday(d.today);
    setSelected((s) => s ?? d.tickets.find((t) => t.state === "open")?.id ?? d.tickets[0]?.id ?? null);
  }, []);
  const loadCash = useCallback(async () => {
    const c = await api.cash();
    setCash(c);
    setCashHistory((h) => (h[h.length - 1] === c.balance ? h : [...h, c.balance].slice(-24)));
  }, []);
  const loadApprovals = useCallback(async () => {
    const a = await api.approvals("all");
    setApprovals(a.approvals);
  }, []);
  const loadTicketView = useCallback(async (id: number, preferRun?: string | null) => {
    const [s, d] = await Promise.all([api.summary(id), api.ticket(id)]);
    setSummary(s); setDetail(d);
    const runId = preferRun ?? s.ticket_run_id;
    if (runId) {
      const ev = await api.events(0, runId);
      setEvents(ev.events); cursor.current = ev.next_since; setWireRunId(runId);
    } else { setEvents([]); cursor.current = 0; setWireRunId(null); }
  }, []);
  const refreshAll = useCallback(async () => {
    try {
      const h = await api.health();
      setAgentsReady(h.agents_ready);
      if (!h.agents_ready && h.agents_error) setOffline(`Agents unavailable: ${h.agents_error}`);
      else setOffline(null);
      await Promise.all([loadTickets(), loadCash(), loadApprovals()]);
      const r = await api.runs();
      if (r.active) { setActiveRun(r.active); setSelected(r.active.ticket_id); }
    } catch (e) {
      setOffline(`Can't reach the backend at ${API_BASE}. Start it with: cd backend && uvicorn main:app --reload --port 8000`);
    }
  }, [loadTickets, loadCash, loadApprovals]);

  useEffect(() => { refreshAll(); }, [refreshAll]);
  useEffect(() => {
    if (selected == null) return;
    if (running && activeRun?.ticket_id === selected) return;
    setView("wire");
    loadTicketView(selected).then(() => {}).catch(() => {});
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------- live polling during a run
  useInterval(async () => {
    if (!activeRun) return;
    try {
      const [ev, r] = await Promise.all([api.events(cursor.current, activeRun.ticket_run_id), api.run(activeRun.ticket_run_id)]);
      if (ev.events.length) setEvents((old) => [...old, ...ev.events]);
      cursor.current = ev.next_since;
      if (ev.events.some((e) => e.tool_calls?.some((c) => c.tool.startsWith("request_")))) loadApprovals();
      setActiveRun(r);
      if (r.status === "done" || r.status === "error") {
        await Promise.all([loadTickets(), loadCash(), loadApprovals()]);
        await loadTicketView(r.ticket_id, r.ticket_run_id);
        setView("recap");
        if (r.status === "done") toast(`Ticket ${r.ticket_id} resolved. The team's recap is ready.`);
        else toast(`Run on ticket ${r.ticket_id} failed: ${r.error}`, "err");
        setActiveRun(null);
      }
    } catch { /* keep polling */ }
  }, 1200, running);

  // light background refresh (cash/approvals) when idle
  useInterval(() => { loadCash().catch(() => {}); loadApprovals().catch(() => {}); }, 6000, !running && !offline);

  // ---------------------------------------------------------------- actions
  const startRun = async (id: number) => {
    try {
      const r = await api.runTicket(id);
      setActiveRun(r); setWireRunId(r.ticket_run_id); setEvents([]); setView("wire");
      const ev = await api.events(0, r.ticket_run_id); cursor.current = ev.next_since; setEvents(ev.events);
      setSummary(null);
      toast(`Ticket ${id} handed to the team. Boss is reading it.`);
    } catch (e) { toast((e as Error).message, "err"); }
  };
  const approve = async (a: Approval) => {
    try {
      const res = await api.approve(a.id, signer.trim());
      if (res.payment.ok) toast(`Paid ${a.payee ?? "#" + a.id}. Checking is now ${res.checking_balance.toLocaleString("en-US", { style: "currency", currency: "USD" })}.`);
      else toast(`Not paid: ${res.payment.message}`, "warn");
    } catch (e) { toast((e as Error).message, "err"); }
    await Promise.all([loadApprovals(), loadCash()]);
    if (selected != null) api.ticket(selected).then(setDetail).catch(() => {});
  };
  const reject = async (a: Approval) => {
    try { await api.reject(a.id, signer.trim(), "voided at the desk"); toast(`Voided cheque #${a.id}. No money moved.`, "warn"); }
    catch (e) { toast((e as Error).message, "err"); }
    await Promise.all([loadApprovals(), loadCash()]);
  };
  const reset = async () => {
    if (!armReset) { setArmReset(true); setTimeout(() => setArmReset(false), 4000); return; }
    setArmReset(false);
    try {
      await api.reset();
      setCashHistory([]); setEvents([]); setSummary(null); setWireRunId(null);
      await refreshAll();
      if (selected != null) await loadTicketView(selected);
      toast("Shop reset to the original books. Fresh start.");
    } catch (e) { toast((e as Error).message, "err"); }
  };

  const sel = tickets.find((t) => t.id === selected) ?? null;
  const showingLive = running && activeRun?.ticket_id === selected;
  const wireEvents = showingLive || wireRunId ? events : [];

  return (
    <div className="desk">
      <header className="top">
        <div className="brand">
          <div className="brand__mark">CC</div>
          <div>
            <div className="brand__name">Campus Customs</div>
            <div className="brand__sub">Operations desk · New Haven</div>
          </div>
        </div>
        <div className="top__day">
          {today && <><span className="k">Shop date</span><span className="top__date">{prettyDate(today)}</span></>}
          <span className={`pulse ${running ? "pulse--on" : ""}`}>{running ? `Team working on #${activeRun?.ticket_id}` : "Floor is quiet"}</span>
        </div>
        <CashTill cash={cash} history={cashHistory} />
        <button className={`btn btn--reset ${armReset ? "btn--armed" : ""}`} onClick={reset} disabled={running}
                title="Restore campus_customs_new.db from the original">{armReset ? "Click again to reset" : "↺ Reset shop"}</button>
      </header>

      {offline && <div className="banner">{offline}</div>}

      <main className="grid">
        <TicketRail tickets={tickets} selected={selected} activeRun={activeRun} onSelect={setSelected} onRun={startRun} agentsReady={agentsReady} />

        <section className="center">
          {sel && (
            <div className="focus">
              <div>
                <div className="focus__kind">{TICKET_TYPE[sel.type]?.glyph} {TICKET_TYPE[sel.type]?.label ?? sel.type} · No. {sel.id}</div>
                <h1 className="focus__title">{sel.subject}</h1>
                <div className="focus__note">“{sel.notes}” <span className="muted">from {sel.requester}</span></div>
              </div>
              <div className={`status status--${sel.state}`}>{sel.state === "resolved" ? "Resolved" : sel.status.replace("_", " ")}</div>
            </div>
          )}
          <AgentFloor events={wireEvents} running={showingLive} />
          <div className="tabs">
            <button className={view === "wire" ? "on" : ""} onClick={() => setView("wire")}>Live wire {showingLive && <span className="dot-live" />}</button>
            <button className={view === "recap" ? "on" : ""} onClick={() => setView("recap")} disabled={showingLive}>Recap</button>
            {wireEvents.length > 0 && <span className="tabs__meta">{wireEvents.filter((e) => e.event === "model_step").length} model steps · run {wireRunId}</span>}
          </div>
          <div className="panel">
            {view === "wire" ? <LiveWire events={wireEvents} running={showingLive} /> : <Recap summary={summary} detail={detail} />}
          </div>
        </section>

        <SignatureTray approvals={approvals} signer={signer} setSigner={setSigner} onApprove={approve} onReject={reject} />
      </main>

      <footer className="foot">Agents prepare · people sign · every step is logged to <code>output/audit_trail.json</code> · all agents run gpt-6-luna via Portkey</footer>

      <div className="toasts">{toasts.map((t) => <div key={t.id} className={`toast toast--${t.tone}`}>{t.text}</div>)}</div>
    </div>
  );
}
