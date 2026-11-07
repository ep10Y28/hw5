import type { AgentEvent, Approval, Cash, Run, Ticket, TicketDetail, TicketSummary } from "./types";

// The FastAPI backend from Problem 7. Override with VITE_API_URL if needed.
export const API_BASE: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((body as { detail?: string }).detail ?? `${res.status} ${res.statusText}`);
  return body as T;
}

export const api = {
  health: () => call<{ ok: boolean; agents_ready: boolean; agents_error: string | null; run_in_progress: boolean }>("/api/health"),
  tickets: () => call<{ today: string; tickets: Ticket[] }>("/api/tickets"),
  ticket: (id: number) => call<TicketDetail>(`/api/tickets/${id}`),
  summary: (id: number) => call<TicketSummary>(`/api/tickets/${id}/summary`),
  runTicket: (id: number) => call<Run>(`/api/tickets/${id}/run`, { method: "POST" }),
  runs: () => call<{ active: Run | null; runs: Run[] }>("/api/runs"),
  run: (runId: string) => call<Run>(`/api/runs/${runId}`),
  events: (since: number, runId?: string) =>
    call<{ total: number; next_since: number; events: AgentEvent[] }>(
      `/api/events?since=${since}&limit=500${runId ? `&ticket_run_id=${runId}` : ""}`,
    ),
  approvals: (status = "all") => call<{ count: number; approvals: Approval[] }>(`/api/approvals?status=${status}`),
  approve: (id: number, approver: string, note = "") =>
    call<{ payment: { ok: boolean; message?: string }; checking_balance: number }>(`/api/approvals/${id}/approve`, {
      method: "POST", body: JSON.stringify({ approver, note }),
    }),
  reject: (id: number, approver: string, note = "") =>
    call(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ approver, note }) }),
  cash: () => call<Cash>("/api/cash"),
  reset: () => call<{ ok: boolean; checking_balance: number }>("/api/reset", { method: "POST" }),
};
