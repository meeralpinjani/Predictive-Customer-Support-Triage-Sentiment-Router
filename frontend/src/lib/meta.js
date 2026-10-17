// Route identity: label + colour always travel together, never colour alone.
// `bar` is a CSS colour that follows the theme (validated light + dark palettes).
export const ROUTES = {
  level3: { label: "Level 3", name: "Expert Escalation", badge: "bg-senior-soft text-senior-text", dot: "bg-senior", bar: "rgb(var(--senior))" },
  level2: { label: "Level 2", name: "Technical Support", badge: "bg-tier2-soft text-tier2-text", dot: "bg-tier2", bar: "rgb(var(--tier2))" },
  level1: { label: "Level 1", name: "General Support", badge: "bg-tier1-soft text-tier1-text", dot: "bg-tier1", bar: "rgb(var(--tier1))" },
  auto_kb: { label: "Auto-answered", name: "Knowledge base", badge: "bg-auto-soft text-auto-text", dot: "bg-auto", bar: "rgb(var(--auto))" },
};
export const ROUTE_ORDER = ["level3", "level2", "level1", "auto_kb"];
export const LEVELS = ["level1", "level2", "level3"];
export const routeMeta = (r) =>
  ROUTES[r] ?? { label: r, name: r, badge: "bg-sunken text-ink-2", dot: "bg-ink-3", bar: "rgb(var(--ink-3))" };
export const levelTitle = (r) => (ROUTES[r] && r !== "auto_kb" ? `${ROUTES[r].label} · ${ROUTES[r].name}` : routeMeta(r).label);

export const ROLE_LABEL = {
  customer: "Customer", level1: "Level 1 · General Support", level2: "Level 2 · Technical Support",
  level3: "Level 3 · Expert Escalation", admin: "Admin",
};
export const isAgentRole = (role) => ["level1", "level2", "level3"].includes(role);
export const homeFor = (user) =>
  !user ? "/login" : user.role === "customer" ? "/support" : user.role === "admin" ? "/admin" : "/queue";

export function timeAgo(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

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
  billing_dispute: "Billing dispute", access: "Login / access", performance: "Performance", integration: "Integration", cancellation: "Cancellation", password_reset: "Password reset",
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
  { label: "Outage", customer_id: "c1", category: "outage", body: "Production DOWN for an hour. Cancelling if not fixed ASAP!!" },
  { label: "Password", customer_id: "c15", category: "account", body: "How do I reset my password?" },
  { label: "Double charge", customer_id: "c14", category: "billing", body: "Charged twice this month, please refund today" },
  { label: "Invoices", customer_id: "c13", category: "billing", body: "Where can I download invoices? Thanks!" },
  { label: "Angry", customer_id: "c15", category: "feedback", body: "This is the worst app, nobody replies!!!" },
  { label: "Security", customer_id: "c14", category: "account", body: "Someone logged into my account from another country" },
  { label: "Slow", customer_id: "c4", category: "performance", body: "The dashboard is very slow today and reports keep timing out." },
  { label: "Hinglish", customer_id: "c16", category: "billing", body: "Mera payment fail ho gaya, kal tak chahiye" },
  { label: "Sarcasm", customer_id: "c4", category: "bug", body: "Great, just great. The export broke again. Thanks for nothing." },
  { label: "Not hacked", customer_id: "c7", category: "account", body: "We were not hacked, I just want to enable two-factor login." },
];
