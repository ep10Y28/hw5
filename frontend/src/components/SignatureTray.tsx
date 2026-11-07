import { useState } from "react";
import { look, money } from "../agents";
import type { Approval } from "../types";

interface Props {
  approvals: Approval[];
  signer: string;
  setSigner: (s: string) => void;
  onApprove: (a: Approval) => Promise<void>;
  onReject: (a: Approval) => Promise<void>;
}

const KIND = { invoice: "Vendor invoice", rent: "Rent", purchase_order: "Purchase order" } as const;

function Cheque({ a, signer, onApprove, onReject }: { a: Approval; signer: string; onApprove: Props["onApprove"]; onReject: Props["onReject"] }) {
  const [busy, setBusy] = useState(false);
  const R = look(a.requested_by);
  const done = a.status !== "pending";
  const stamp = { executed: "Paid", rejected: "Void", refused: "Refused", approved: "Approved", pending: "" }[a.status];
  const act = async (f: () => Promise<void>) => { setBusy(true); try { await f(); } finally { setBusy(false); } };
  return (
    <div className={`cheque ${done ? "cheque--done" : ""} cheque--${a.status}`}>
      <div className="cheque__top">
        <span className="cheque__bank">Campus Customs · Checking</span>
        <span className="cheque__no">No. {String(a.id).padStart(4, "0")}</span>
      </div>
      <div className="cheque__pay">
        <span className="k">Pay to the order of</span>
        <span className="cheque__payee">{a.payee ?? KIND[a.kind]}</span>
        <span className="cheque__amt">{money(a.amount)}</span>
      </div>
      <div className="cheque__memo"><span className="k">Memo</span>{a.memo ?? a.reason}</div>
      <div className="cheque__by">
        <span>{KIND[a.kind]} · ticket {a.ticket_id}</span>
        <span>prepared by <b style={{ color: R.color }}>{R.label}</b></span>
      </div>
      {!done ? (
        <div className="cheque__sign">
          <div className="sigline">{signer ? <span className="sig">{signer}</span> : <span className="muted">sign your name above to approve</span>}</div>
          <div className="cheque__btns">
            <button className="btn btn--ghost" disabled={busy || !signer} onClick={() => act(() => onReject(a))}>Void</button>
            <button className="btn btn--sign" disabled={busy || !signer} onClick={() => act(() => onApprove(a))}>{busy ? "Paying…" : "Sign & pay"}</button>
          </div>
        </div>
      ) : (
        <div className="cheque__decided">{a.decided_by ? <>by <span className="sig sig--sm">{a.decided_by}</span></> : null}{a.decision_note ? <span className="muted"> · {a.decision_note}</span> : null}</div>
      )}
      {stamp && <div className={`stamp stamp--${a.status}`}>{stamp}</div>}
    </div>
  );
}

/** Right side: payments the agents prepared, drawn as cheques waiting for a person's signature. */
export function SignatureTray({ approvals, signer, setSigner, onApprove, onReject }: Props) {
  const pending = approvals.filter((a) => a.status === "pending");
  const done = approvals.filter((a) => a.status !== "pending").slice().reverse();
  return (
    <aside className="tray">
      <div className="tray__head">
        <h2>Needs your signature</h2>
        <span className={`badge ${pending.length ? "badge--hot" : ""}`}>{pending.length}</span>
      </div>
      <label className="signer">
        <span>Signing as</span>
        <input value={signer} placeholder="your name" onChange={(e) => setSigner(e.target.value)} />
      </label>
      <p className="tray__note">Agents only prepare payments. Nothing leaves the till until a person signs.</p>
      {pending.length === 0 && <div className="empty empty--tray">Nothing waiting. Cheques appear here when Accounting prepares one.</div>}
      {pending.map((a) => <Cheque key={a.id} a={a} signer={signer} onApprove={onApprove} onReject={onReject} />)}
      {done.length > 0 && <h3 className="tray__sub">Signed today</h3>}
      {done.map((a) => <Cheque key={a.id} a={a} signer={signer} onApprove={onApprove} onReject={onReject} />)}
    </aside>
  );
}
