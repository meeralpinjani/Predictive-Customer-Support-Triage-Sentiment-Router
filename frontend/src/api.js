// Same-origin by default: Vite (dev) and nginx (Docker) proxy /api to the backend,
// so the HttpOnly session cookie just works. VITE_API_URL can point elsewhere if needed.
const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg.replace(/^Value error, /, "")).join("; ") : String(body.detail);
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const patch = (path, body) => request(path, { method: "PATCH", body: JSON.stringify(body ?? {}) });
const del = (path) => request(path, { method: "DELETE" });

/** multipart upload: files (File[]) plus optional text fields. */
async function upload(path, files, fields = {}) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { method: "POST", credentials: "include", body: fd });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join("; ") : String(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

export const MAX_FILES = 5;
export const MAX_MB = 5;
export const ACCEPT = "image/png,image/jpeg,application/pdf";

export const eventsUrl = `${BASE}/api/events`;

export const api = {
  // accounts
  authConfig: () => request("/api/auth/config"),
  me: () => request("/api/auth/me"),
  login: (email, password, remember = false) => post("/api/auth/login", { email, password, remember }),
  forgot: (email) => post("/api/auth/forgot", { email }),
  resetPassword: (token, password) => post("/api/auth/reset", { token, password }),
  setAvailability: (availability) => patch("/api/auth/me/availability", { availability }),
  workload: () => request("/api/admin/users/workload/summary"),
  signup: (payload) => post("/api/auth/signup", payload),
  google: (credential) => post("/api/auth/google", { credential }),
  logout: () => post("/api/auth/logout"),
  updateMe: (payload) => patch("/api/auth/me", payload),
  users: () => request("/api/admin/users"),
  updateUser: (id, payload) => patch(`/api/admin/users/${id}`, payload),

  // reference
  health: () => request("/api/health"),
  categories: () => request("/api/categories"),
  config: () => request("/api/config"),
  customers: () => request("/api/customers"),
  kbArticles: () => request("/api/kb-articles"),
  createArticle: (payload) => post("/api/kb-articles", payload),
  updateArticle: (id, payload) => patch(`/api/kb-articles/${id}`, payload),
  deleteArticle: (id) => del(`/api/kb-articles/${id}`),
  kbSuggest: (q) => request(`/api/kb/suggest?${new URLSearchParams({ q })}`),
  kbTopics: () => request("/api/kb/topics"),
  search: (q) => request(`/api/search?${new URLSearchParams({ q })}`),
  stats: () => request("/api/stats"),
  evaluation: () => request("/api/eval"),

  // customers
  myTickets: () => request("/api/my/tickets"),
  myTicket: (id) => request(`/api/my/tickets/${id}`),
  feedback: (id, kind) => post(`/api/tickets/${id}/feedback`, { kind }),

  // tickets (staff)
  tickets: (params = {}) => request(`/api/tickets?${new URLSearchParams(params)}`),
  ticket: (id) => request(`/api/tickets/${id}`),
  submitTicket: (payload) => post("/api/tickets", payload),
  claim: (id) => post(`/api/tickets/${id}/claim`),
  escalate: (id, reason) => post(`/api/tickets/${id}/escalate`, { reason }),
  override: (id, payload) => post(`/api/tickets/${id}/override`, payload),
  resolve: (id) => post(`/api/tickets/${id}/resolve`),

  // conversation & calls
  messages: (id) => request(`/api/tickets/${id}/messages`),
  sendMessage: (id, body) => post(`/api/tickets/${id}/messages`, { body }),
  sendMessageWithFiles: (id, body, files) => upload(`/api/tickets/${id}/messages/upload`, files, { body }),
  uploadTicketFiles: (id, files) => upload(`/api/tickets/${id}/attachments`, files),
  suggestedReply: (id) => request(`/api/tickets/${id}/suggested-reply`),
  guides: (id) => request(`/api/tickets/${id}/guides`),
  typing: (id) => post(`/api/tickets/${id}/typing`),
  callbacks: (id) => request(`/api/tickets/${id}/callbacks`),
  requestCallback: (id, payload) => post(`/api/tickets/${id}/callbacks`, payload),
  updateCallback: (id, cbId, status) => patch(`/api/tickets/${id}/callbacks/${cbId}`, { status }),

  // incidents
  incidentSuggestions: () => request("/api/incidents/suggestions"),
  incidents: () => request("/api/incidents"),
  createIncident: (ticket_ids, title) => post("/api/incidents", { ticket_ids, title }),
  incidentReply: (id, body) => post(`/api/incidents/${id}/reply`, { body }),
  incidentResolve: (id, body) => post(`/api/incidents/${id}/resolve`, { body }),

  // admin tools
  analytics: (days = 7) => request(`/api/admin/analytics?days=${days}`),
  outbox: () => request("/api/admin/outbox"),
  retrain: () => request("/api/admin/retrain"),
  retrainApply: (payload) => post("/api/admin/retrain/apply", payload),
  kbMatch: (text) => post("/api/kb/test-match", { text }),
  whatIf: (payload) => post("/api/whatif", payload),
  rescore: () => post("/api/admin/rescore"),
};
