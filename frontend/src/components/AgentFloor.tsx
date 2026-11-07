import { AGENT_ORDER, look, TOOL_VERBS } from "../agents";
import type { AgentEvent, AgentName } from "../types";

export type SeatState = "idle" | "working" | "waiting" | "done" | "error";

/** Works out each agent's state and latest line from the run's events. */
export function seatStates(events: AgentEvent[]) {
  const state: Record<string, SeatState> = {};
  const line: Record<string, string> = {};
  const stack: string[] = [];
  for (const e of events) {
    const a = e.agent;
    if (e.event === "run_start") { state[a] = "working"; stack.push(a); }
    if (e.event === "delegation") { state[a] = "waiting"; line[a] = `asked ${look(e.delegated_to ?? "").label}`; }
    if (e.event === "model_step") {
      const tool = e.tool_calls?.find((c) => c.tool !== "final_result");
      if (tool && tool.tool !== "delegate") line[a] = TOOL_VERBS[tool.tool] ?? tool.tool;
      else if (e.text) line[a] = e.text;
      if (state[a] === "waiting") state[a] = "working";
    }
    if (e.event === "tool_results" && state[a] === "waiting") state[a] = "working";
    if (e.event === "run_end") { state[a] = "done"; line[a] = "reported back"; stack.pop(); }
    if (e.event === "error") { state[a] = "error"; line[a] = "hit an error"; }
  }
  const speaking = [...stack].reverse().find((a) => state[a] === "working") ?? null;
  return { state, line, speaking };
}

export function AgentFloor({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const { state, line, speaking } = seatStates(events);
  const lastHandoff = [...events].reverse().find((e) => e.event === "delegation");
  return (
    <section className="floor">
      <div className="floor__seats">
        {AGENT_ORDER.map((name: AgentName) => {
          const L = look(name);
          const s = state[name] ?? "idle";
          return (
            <div key={name} className={`seat seat--${s} ${speaking === name ? "seat--speaking" : ""} ${name === "boss" ? "seat--boss" : ""}`}
                 style={{ ["--c" as string]: L.color, ["--t" as string]: L.tint }}>
              <div className="seat__avatar"><span>{L.monogram}</span>{s === "done" && <em>✓</em>}</div>
              <div className="seat__name">{L.label}</div>
              <div className="seat__role">{L.role}</div>
              <div className="seat__line">
                {s === "idle" ? (running ? "on standby" : "at their desk")
                  : speaking === name ? <>{line[name] ?? "thinking"} <span className="dots"><i /><i /><i /></span></>
                  : s === "waiting" ? <>{line[name]} · waiting</>
                  : line[name] ?? s}
              </div>
            </div>
          );
        })}
      </div>
      <div className="floor__handoff">
        {lastHandoff ? (
          <>
            <span style={{ color: look(lastHandoff.agent).color }}>{look(lastHandoff.agent).label}</span>
            <span className="arrow">⟶</span>
            <span style={{ color: look(lastHandoff.delegated_to ?? "").color }}>{look(lastHandoff.delegated_to ?? "").label}</span>
            <span className="muted">latest hand-off</span>
          </>
        ) : <span className="muted">{running ? "Boss is reading the ticket…" : "Pick a ticket and hand it to the team. Boss routes it from there."}</span>}
      </div>
    </section>
  );
}
