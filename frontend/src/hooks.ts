import { useEffect, useRef, useState } from "react";

/** Smoothly animates a number toward `target` (used for the cash till). */
export function useAnimatedNumber(target: number | null, ms = 900): number | null {
  const [value, setValue] = useState<number | null>(target);
  const from = useRef<number | null>(target);
  useEffect(() => {
    if (target == null) return;
    const start = from.current ?? target;
    if (start === target) { setValue(target); return; }
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      const eased = 1 - Math.pow(1 - k, 3);
      const v = start + (target - start) * eased;
      setValue(v);
      if (k < 1) raf = requestAnimationFrame(tick);
      else from.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return value;
}

/** Calls fn every `ms` while `active` is true. */
export function useInterval(fn: () => void, ms: number, active = true) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => saved.current(), ms);
    return () => clearInterval(id);
  }, [ms, active]);
}

/** localStorage that never throws (some browsers block it). */
export function loadPref(key: string, fallback: string): string {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
export function savePref(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* ignore */ }
}
