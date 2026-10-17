// Route identity: label + colour always travel together, never colour alone.
export const ROUTES = {
  senior: { label: "Senior", short: "SR", dot: "bg-nordic-lingonberry", badge: "bg-nordic-lingonberryLight text-nordic-lingonberry", bar: "#BE123C" },
  tier2: { label: "Tier 2", short: "T2", dot: "bg-nordic-cloudberry", badge: "bg-nordic-cloudberryLight text-amber-800", bar: "#D97706" },
  tier1: { label: "Tier 1", short: "T1", dot: "bg-nordic-pine", badge: "bg-nordic-pineLight text-teal-800", bar: "#0D9488" },
  auto_kb: { label: "Auto KB", short: "KB", dot: "bg-nordic-aurora", badge: "bg-nordic-auroraLight text-nordic-aurora", bar: "#4F46E5" },
};

export const ROUTE_ORDER = ["senior", "tier2", "tier1", "auto_kb"];

export const routeMeta = (r) => ROUTES[r] ?? { label: r, short: "?", dot: "bg-slate-400", badge: "bg-slate-100 text-slate-600", bar: "#64748B" };

export const STATUS_LABEL = {
  queued: "Queued",
  in_progress: "In progress",
  kb_handled: "Auto-answered",
  resolved: "Resolved",
  new: "New",
};

export const SEGMENT_LABEL = {
  enterprise: "Enterprise",
  pro: "Pro",
  basic: "Basic",
  free: "Free",
  unknown: "Unknown",
};

export const COMPONENT_LABEL = {
  urgency: "Urgency",
  frustration: "Frustration",
  value: "Customer value",
  age: "Wait vs SLA",
};

export const OPEN_STATUSES = ["queued", "in_progress"];

export function fmtWait(min) {
  if (min == null) return "–";
  if (min < 1) return "<1m";
  if (min < 60) return `${Math.round(min)}m`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}

export const pct = (x, digits = 0) => `${(x * 100).toFixed(digits)}%`;

// Demo tickets from the playbook's seed set (section 6.7).
export const EXAMPLES = [
  { label: "Outage", customer_id: "c1", subject: "Production dashboard down", body: "Our production dashboard has been DOWN for an hour. We will cancel if this is not fixed ASAP!" },
  { label: "Password", customer_id: "c9", subject: "", body: "How do I reset my password?" },
  { label: "Double charge", customer_id: "c3", subject: "", body: "I was charged twice this month. Please refund today." },
  { label: "Invoices", customer_id: "c4", subject: "", body: "Where can I download invoices? Thanks!" },
  { label: "Angry", customer_id: "c10", subject: "", body: "This is the worst app, nothing works and nobody replies!!!" },
  { label: "Security", customer_id: "c3", subject: "", body: "Someone logged into my account from another country." },
  { label: "Feature", customer_id: "c5", subject: "", body: "Would be nice to have dark mode." },
];
