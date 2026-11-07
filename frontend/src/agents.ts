import type { AgentName } from "./types";

export interface AgentLook {
  name: AgentName;
  label: string;
  role: string;
  monogram: string;
  color: string;   // ink colour for this agent
  tint: string;    // soft background
  voice: "lead" | "count" | "ledger" | "build" | "warm";
}

// Each agent gets its own colour, monogram and "voice" (type treatment), so you
// can tell who is talking at a glance without reading the name.
export const AGENTS: Record<AgentName, AgentLook> = {
  boss: { name: "boss", label: "Boss", role: "Routes tickets · makes the call", monogram: "B",
    color: "#0f2d52", tint: "#e7edf6", voice: "lead" },
  inventory: { name: "inventory", label: "Inventory", role: "Stock · sizes · restock", monogram: "In",
    color: "#1b6f6a", tint: "#e3f2f0", voice: "count" },
  accounting: { name: "accounting", label: "Accounting", role: "Cash · invoices · margins", monogram: "Ac",
    color: "#3d6b2c", tint: "#eaf3e4", voice: "ledger" },
  facilities: { name: "facilities", label: "Facilities", role: "Lease · rent · the space", monogram: "Fa",
    color: "#a4502b", tint: "#f8ebe3", voice: "build" },
  customer_service: { name: "customer_service", label: "Customer Service", role: "Drafts for customers", monogram: "CS",
    color: "#7b3c8c", tint: "#f3e9f6", voice: "warm" },
};

export const AGENT_ORDER: AgentName[] = ["boss", "inventory", "accounting", "facilities", "customer_service"];

export function look(agent: string): AgentLook {
  return (AGENTS as Record<string, AgentLook>)[agent] ?? {
    name: agent as AgentName, label: agent === "human" ? "You" : agent, role: "", monogram: agent === "human" ? "✎" : "?",
    color: "#6b5b3e", tint: "#f5efe2", voice: "lead",
  };
}

// Friendly verbs for MCP tools, used on the live wire.
export const TOOL_VERBS: Record<string, string> = {
  get_ticket: "opened the ticket",
  list_open_tickets: "scanned the board",
  list_tickets: "scanned the board",
  update_ticket_status: "moved the ticket",
  check_stock_by_size: "counted stock",
  list_vendors: "checked vendors",
  get_vendor_invoice_status: "checked the vendor's account",
  get_lease_rent_due: "pulled the lease",
  get_price_and_margin: "ran the margin",
  get_invoice: "pulled the invoice",
  get_cash_position: "checked the till",
  list_approvals: "looked at pending approvals",
  request_payment: "prepared a payment for your signature",
  request_purchase_order: "prepared a purchase order",
  post_to_board: "posted to the board",
  delegate: "handed off work",
};

export const TICKET_TYPE: Record<string, { label: string; glyph: string }> = {
  customer_order: { label: "Customer order", glyph: "🛍" },
  rent_notice: { label: "Rent notice", glyph: "🏛" },
  price_override: { label: "Discount request", glyph: "🏷" },
};

export const money = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString("en-US", { style: "currency", currency: "USD" });
