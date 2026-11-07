import { useEffect, useRef, useState } from "react";
import { money } from "../agents";
import { useAnimatedNumber } from "../hooks";
import type { Cash } from "../types";

/** The till: checking balance in big ledger numerals, with a drop animation and a tiny history line. */
export function CashTill({ cash, history }: { cash: Cash | null; history: number[] }) {
  const shown = useAnimatedNumber(cash?.balance ?? null);
  const prev = useRef<number | null>(null);
  const [delta, setDelta] = useState<number | null>(null);

  useEffect(() => {
    if (cash == null) return;
    if (prev.current != null && cash.balance !== prev.current) {
      setDelta(cash.balance - prev.current);
      const id = setTimeout(() => setDelta(null), 3200);
      prev.current = cash.balance;
      return () => clearTimeout(id);
    }
    prev.current = cash.balance;
  }, [cash]);

  const pts = history.length > 1 ? history : [cash?.balance ?? 0, cash?.balance ?? 0];
  const max = Math.max(...pts), min = Math.min(...pts, 0);
  const path = pts.map((v, i) => {
    const x = (i / (pts.length - 1)) * 120;
    const y = 30 - ((v - min) / (max - min || 1)) * 26 - 2;
    return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return (
    <div className={`till ${delta != null ? (delta < 0 ? "till--drop" : "till--rise") : ""}`}>
      <div className="till__label">Checking · cash on hand</div>
      <div className="till__row">
        <div className="till__amount">{shown == null ? "—" : money(shown)}</div>
        {delta != null && <div className={`till__delta ${delta < 0 ? "neg" : "pos"}`}>{delta < 0 ? "−" : "+"}{money(Math.abs(delta))}</div>}
        <svg className="till__spark" viewBox="0 0 120 32" aria-hidden><path d={path} /></svg>
      </div>
      {cash && (
        <div className="till__sub">
          <span>Promised to pending approvals <b>{money(cash.reserved_by_pending_approvals)}</b></span>
          <span>Free <b className={cash.available_after_reserved < 300 ? "warn" : ""}>{money(cash.available_after_reserved)}</b></span>
        </div>
      )}
    </div>
  );
}
