import { look } from "../agents";
import type { BoardPost, TicketDetail, TicketSummary } from "../types";

function Letter({ post }: { post: BoardPost }) {
  return (
    <div className="letter">
      <div className="letter__head">
        <span>To: <b>{post.recipient ?? "customer"}</b></span>
        <span className="letter__stamp">Draft · not sent</span>
      </div>
      <p>{post.body}</p>
      <div className="letter__foot">drafted by {look(post.author).label} · a person reviews and sends</div>
    </div>
  );
}

/** After a run: Boss's call up top, then one card per agent saying what it did. */
export function Recap({ summary, detail }: { summary: TicketSummary | null; detail: TicketDetail | null }) {
  if (!summary || summary.agents.length === 0) {
    return <div className="empty">No finished run yet. The recap appears here when the team reports back.</div>;
  }
  const o = summary.outcome;
  const drafts = (detail?.board ?? []).filter((b) => b.kind === "draft_message");
  return (
    <div className="recap">
      {o && (
        <div className="verdict">
          <div className="verdict__label">Boss's call · ticket {o.ticket_id}</div>
          <p className="verdict__text">{o.decision}</p>
          {o.needs_human.length > 0 && (
            <div className="verdict__todo">
              <div className="verdict__todo-h">Left for a person</div>
              <ul>{o.needs_human.map((n, i) => <li key={i}>{n}</li>)}</ul>
            </div>
          )}
        </div>
      )}
      <div className="recap__grid">
        {summary.agents.map((a) => {
          const L = look(a.agent);
          return (
            <div key={a.agent} className={`card voice-${L.voice}`} style={{ ["--c" as string]: L.color, ["--t" as string]: L.tint }}>
              <div className="card__head">
                <span className="chip-avatar">{L.monogram}</span>
                <div><div className="card__name">{L.label}</div><div className="card__meta">{a.steps} steps · {a.tools_used.length} tools{a.blocked_actions ? ` · ${a.blocked_actions} blocked` : ""}</div></div>
              </div>
              <p className="card__summary">{a.summary ?? (a.status === "running" ? "still working…" : "—")}</p>
              {a.delegated_to.length > 0 && (
                <div className="card__row"><span className="k">Handed to</span>{a.delegated_to.map((d, i) => <span key={i} className="pill" style={{ color: look(d).color, background: look(d).tint }}>{look(d).label}</span>)}</div>
              )}
              {a.tools_used.length > 0 && (
                <div className="card__row"><span className="k">Tools</span>{a.tools_used.map((t) => <code key={t} className="tool">{t}</code>)}</div>
              )}
              {(a.approval_ids.length > 0 || a.board_ids.length > 0) && (
                <div className="card__row"><span className="k">Created</span>
                  {a.approval_ids.map((id) => <span key={`a${id}`} className="pill pill--gold">approval #{id}</span>)}
                  {a.board_ids.map((id) => <span key={`b${id}`} className="pill">board #{id}</span>)}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {drafts.length > 0 && (
        <div className="drafts">
          <h3>Customer drafts</h3>
          {drafts.map((d) => <Letter key={d.id} post={d} />)}
        </div>
      )}
    </div>
  );
}
