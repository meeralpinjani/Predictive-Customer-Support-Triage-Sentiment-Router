// Route identity: label + colour always travel together, never colour alone.
// `bar` is a CSS colour that follows the theme (validated light + dark palettes).
export const ROUTES = {
  senior: { label: "Senior", badge: "bg-senior-soft text-senior-text", dot: "bg-senior", bar: "rgb(var(--senior))" },
  tier2: { label: "Tier 2", badge: "bg-tier2-soft text-tier2-text", dot: "bg-tier2", bar: "rgb(var(--tier2))" },
  tier1: { label: "Tier 1", badge: "bg-tier1-soft text-tier1-text", dot: "bg-tier1", bar: "rgb(var(--tier1))" },
  auto_kb: { label: "Auto KB", badge: "bg-auto-soft text-auto-text", dot: "bg-auto", bar: "rgb(var(--auto))" },
};
export const ROUTE_ORDER = ["senior", "tier2", "tier1", "auto_kb"];
export const routeMeta = (r) =>
  ROUTES[r] ?? { label: r, badge: "bg-sunken text-ink-2", dot: "bg-ink-3", bar: "rgb(var(--ink-3))" };

export const STATUS_LABEL = {
  queued: "Queued",
  in_progress: "In progress",
  kb_handled: "Auto-answered",
  resolved: "Resolved",
  new: "New",
};
export const SEGMENT_LABEL = { enterprise: "Enterprise", pro: "Pro", basic: "Basic", free: "Free", unknown: "Unknown" };
export const COMPONENT_LABEL = { frustration: "Frustration", urgency: "Urgency", value: "Customer value", age: "Wait vs SLA" };
export const COMPONENT_ORDER = ["frustration", "urgency", "value", "age"];
export const BOOST_LABEL = { repeat_contact: "Repeat contact", renewal_risk: "Renewal at risk", sla_risk: "SLA at risk" };
export const SIGNAL_LABEL = { neg: "Negative tone", anger: "Anger / sarcasm", style: "Shouting (CAPS, !!!)", churn: "Churn threat" };
export const VALUE_LABEL = { plan: "Plan tier", ltv: "Lifetime value", churn: "Churn risk", renewal: "Renewal soon" };
export const INTENT_LABEL = {
  billing_dispute: "Billing dispute", access: "Login / access", cancellation: "Cancellation", password_reset: "Password reset",
  invoice: "Invoice", bug: "Bug", complaint: "Complaint", how_to: "How-to", feature_request: "Feature request",
  security: "Security", legal: "Legal", safety: "Safety", outage: "Outage", other: "Other",
};
export const OPEN_STATUSES = ["queued", "in_progress"];
export const isOpen = (t) => OPEN_STATUSES.includes(t.status);

export function fmtWait(min) {
  if (min == null || Number.isNaN(min)) return "–";
  if (min < 1) return "<1m";
  if (min < 60) return `${Math.round(min)}m`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}
export const pct = (x, digits = 0) => (x == null ? "–" : `${(x * 100).toFixed(digits)}%`);

// Demo tickets from the playbook's seed set (section 6.7).
export const EXAMPLES = [
  { label: "Outage", customer_id: "c1", body: "Production DOWN for an hour. Cancelling if not fixed ASAP!!" },
  { label: "Password", customer_id: "c15", body: "How do I reset my password?" },
  { label: "Double charge", customer_id: "c14", body: "Charged twice this month, please refund today" },
  { label: "Invoices", customer_id: "c13", body: "Where can I download invoices? Thanks!" },
  { label: "Angry", customer_id: "c15", body: "This is the worst app, nobody replies!!!" },
  { label: "Security", customer_id: "c14", body: "Someone logged into my account from another country" },
  { label: "Feature", customer_id: "c13", body: "Would be nice to have dark mode" },
  { label: "Hinglish", customer_id: "c16", body: "Mera payment fail ho gaya, kal tak chahiye" },
  { label: "Sarcasm", customer_id: "c4", body: "Great, just great. The export broke again. Thanks for nothing." },
  { label: "Not hacked", customer_id: "c7", body: "We were not hacked, I just want to enable two-factor login." },
];
