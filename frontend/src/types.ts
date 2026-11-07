export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  status: string;
  state: "open" | "resolved";
  notes: string | null;
}

export interface ToolCall { tool: string; args: string }
export interface ToolResult { tool: string; result?: string; retry?: string }

export interface AgentEvent {
  index: number;
  time: string;
  ticket_id: number | null;
  ticket_run_id: string | null;
  agent: AgentName | "human" | string;
  event: string;
  step: number | null;
  chain: string[] | null;
  delegated_to: AgentName | null;
  text: string | null;
  tool_calls: ToolCall[] | null;
  tool_results: ToolResult[] | null;
  stop_reason: string | null;
  tokens: { input: number; output: number } | null;
  ticket_usage: { requests: number; input_tokens: number; output_tokens: number } | null;
  output?: { summary?: string; decision?: string } | null;
}

export interface Run {
  ticket_run_id: string;
  ticket_id: number;
  status: "queued" | "running" | "done" | "error";
  started: string;
  outcome?: TicketOutcome;
  error?: string;
}

export interface TicketOutcome {
  ticket_id: number;
  decision: string;
  agents_consulted: AgentName[];
  actions_taken: string[];
  approval_ids: number[];
  board_ids: number[];
  final_status: string;
  needs_human: string[];
}

export interface AgentRecap {
  agent: AgentName;
  summary: string | null;
  tools_used: string[];
  delegated_to: AgentName[];
  approval_ids: number[];
  board_ids: number[];
  blocked_actions: number;
  steps: number;
  tokens: number;
  status: "running" | "done" | "error";
}

export interface TicketSummary {
  ticket_id: number;
  ticket_run_id: string | null;
  started?: string;
  finished?: string;
  outcome: TicketOutcome | null;
  agents: AgentRecap[];
}

export interface BoardPost {
  id: number;
  ticket_id: number;
  kind: "draft_message" | "note" | "decision";
  author: AgentName;
  recipient: string | null;
  body: string;
  created_at: string;
}

export interface TicketDetail {
  found: boolean;
  today: string;
  ticket: Ticket & { lease_id: number | null; invoice_id: number | null; created_at: string };
  board: BoardPost[];
  approvals: Approval[];
}

export interface Approval {
  id: number;
  kind: "invoice" | "rent" | "purchase_order";
  ref_id: number | null;
  ticket_id: number | null;
  vendor_id: number | null;
  sku: string | null;
  size: string | null;
  qty: number | null;
  amount: number;
  reason: string;
  requested_by: AgentName;
  requested_at: string;
  status: "pending" | "approved" | "rejected" | "executed" | "refused";
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  payment_id: number | null;
  payee?: string;
  memo?: string;
}

export interface Cash {
  account: string;
  balance: number;
  as_of: string;
  reserved_by_pending_approvals: number;
  available_after_reserved: number;
  open_obligations_total: number;
}
