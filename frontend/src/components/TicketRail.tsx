import { TICKET_TYPE } from "../agents";
import type { Run, Ticket } from "../types";

interface Props {
  tickets: Ticket[];
  selected: number | null;
  activeRun: Run | null;
  onSelect: (id: number) => void;
  onRun: (id: number) => void;
  agentsReady: boolean;
}

/** Left rail: each ticket is a paper stub. Resolved tickets get a rubber stamp. */
export function TicketRail({ tickets, selected, activeRun, onSelect, onRun, agentsReady }: Props) {
  const openCount = tickets.filter((t) => t.state === "open").length;
  return (
    <aside className="rail">
      <div className="rail__head">
        <h2>Ticket spike</h2>
        <span className="rail__count">{openCount} open · {tickets.length - openCount} resolved</span>
      </div>
      {tickets.map((t) => {
        const kind = TICKET_TYPE[t.type] ?? { label: t.type, glyph: "•" };
        const running = activeRun?.ticket_id === t.id && (activeRun.status === "running" || activeRun.status === "queued");
        const isSel = selected === t.id;
        return (
          <div key={t.id} className={`stub ${isSel ? "stub--sel" : ""} ${t.state === "resolved" ? "stub--done" : ""} ${running ? "stub--running" : ""}`}
               onClick={() => onSelect(t.id)} role="button" tabIndex={0}
               onKeyDown={(e) => e.key === "Enter" && onSelect(t.id)}>
            <div className="stub__num"><span>No.</span>{t.id}</div>
            <div className="stub__body">
              <div className="stub__kind"><span aria-hidden>{kind.glyph}</span> {kind.label}</div>
              <div className="stub__subject">{t.subject}</div>
              <div className="stub__from">from {t.requester}</div>
              {t.sku && <div className="stub__item">{t.sku} · {t.size} · ×{t.qty}</div>}
              {isSel && t.state === "open" && (
                <button className="btn btn--send" disabled={!agentsReady || !!running || (activeRun != null && (activeRun.status === "running" || activeRun.status === "queued"))}
                        onClick={(e) => { e.stopPropagation(); onRun(t.id); }}>
                  {running ? "Team is on it…" : "Hand to the team →"}
                </button>
              )}
              {running && <div className="stub__live"><i />live</div>}
            </div>
            {t.state === "resolved" && <div className="stamp">Resolved</div>}
          </div>
        );
      })}
    </aside>
  );
}
