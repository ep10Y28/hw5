import { useEffect, useRef } from "react";
import { look, TOOL_VERBS } from "../agents";
import type { AgentEvent } from "../types";

function tryJson(s?: string | null): Record<string, unknown> | null {
  if (!s) return null;
  try { const v = JSON.parse(s.replace(/…$/, "")); return typeof v === "object" && v ? v as Record<string, unknown> : null; } catch { return null; }
}

/** Older audit entries only kept the report as (possibly cut-off) JSON text:
 *  pull out the "summary" or "decision" string instead of showing raw JSON. */
export function fromJsonText(text?: string | null): string {
  if (!text) return "";
  if (!text.trimStart().startsWith("{")) return text;
  const m = text.match(/"(?:summary|decision)":\s*"((?:[^"\\]|\\.)*)/);
  if (!m) return text;
  try { return JSON.parse(`"${m[1].replace(/\\$/, "")}"`); } catch { return m[1]; }
}

function argSummary(args: string): string {
  const a = tryJson(args);
  if (!a) return args.length > 80 ? args.slice(0, 80) + "…" : args;
  const drop = new Set(["requested_by", "author", "updated_by", "body", "reason", "note", "task"]);
  return Object.entries(a).filter(([k]) => !drop.has(k)).map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`).join("  ");
}

function Bubble({ e }: { e: AgentEvent }) {
  const L = look(e.agent);
  const style = { ["--c" as string]: L.color, ["--t" as string]: L.tint };
  const who = <div className="msg__who"><span className="chip-avatar">{L.monogram}</span>{L.label}</div>;

  if (e.event === "run_start") {
    return <div className="wire-sys" style={style}><b>{L.label}</b> sat down · <span className="muted">"{e.text}"</span></div>;
  }
  if (e.event === "delegation") {
    const T = look(e.delegated_to ?? "");
    return (
      <div className="handoff" style={style}>
        <div className="handoff__route"><span style={{ color: L.color }}>{L.label}</span> hands off to <span style={{ color: T.color }}>{T.label}</span></div>
        <blockquote>{e.text}</blockquote>
      </div>
    );
  }
  if (e.event === "model_step") {
    const calls = (e.tool_calls ?? []).filter((c) => c.tool !== "delegate");
    const final = calls.find((c) => c.tool === "final_result");
    const work = calls.filter((c) => c.tool !== "final_result");
    if (!e.text && work.length === 0) return null;
    return (
      <div className={`msg voice-${L.voice}`} style={style}>
        {who}
        {e.text && <p className="msg__text">{e.text}</p>}
        {work.map((c, i) => (
          <div key={i} className="receipt">
            <span className="receipt__verb">{TOOL_VERBS[c.tool] ?? c.tool}</span>
            <code>{c.tool}</code><span className="receipt__args">{argSummary(c.args)}</span>
          </div>
        ))}
        {final && !e.text && <p className="msg__text muted">writing up the report…</p>}
      </div>
    );
  }
  if (e.event === "tool_results") {
    const rs = (e.tool_results ?? []).filter((r) => r.tool !== "delegate" && !r.tool.startsWith("final_result"));
    if (!rs.length) return null;
    return (
      <div className="results" style={style}>
        {rs.map((r, i) => (
          <div key={i} className={`result ${r.retry ? "result--retry" : ""}`}>
            <span className="result__tool">↳ {r.tool}</span>
            <span className="result__body">{r.retry ?? r.result}</span>
          </div>
        ))}
      </div>
    );
  }
  if (e.event === "guardrail") {
    return <div className="guard" style={style}><b>Guardrail</b> stopped {L.label}: {e.text}</div>;
  }
  if (e.event === "run_end") {
    const summary = e.output?.summary ?? e.output?.decision ?? fromJsonText(e.text);
    return (
      <div className={`msg msg--report voice-${L.voice}`} style={style}>
        {who}
        <div className="msg__tag">{e.agent === "boss" ? "Final call" : "Report"}</div>
        <p className="msg__text">{summary}</p>
      </div>
    );
  }
  if (e.event === "ticket_closed") {
    return <div className="wire-sys wire-sys--closed">Ticket marked <b>resolved</b>. The team's part is done.</div>;
  }
  if (e.event === "error") {
    return <div className="guard guard--err" style={style}><b>{L.label} hit an error</b> {e.text}</div>;
  }
  return null;
}

/** The live wire: a transcript of the run, auto-scrolling as agents work. */
export function LiveWire({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  // scroll the transcript itself (not the whole page) to the newest line
  useEffect(() => { const el = box.current; if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }); }, [events.length]);
  return (
    <div className="wire" ref={box}>
      {events.length === 0 && <div className="empty">{running ? "Waiting for Boss to pick up the ticket…" : "No run yet for this ticket. Hand it to the team to watch them work."}</div>}
      {events.map((e) => <Bubble key={e.index} e={e} />)}
      {running && <div className="wire-typing"><span className="dots"><i /><i /><i /></span> agents working</div>}
    </div>
  );
}
