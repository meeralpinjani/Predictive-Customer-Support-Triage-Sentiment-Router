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

export const eventsUrl = `${BASE}/api/events`;

export const api = {
  // accounts
  authConfig: () => request("/api/auth/config"),
  me: () => request("/api/auth/me"),
  login: (email, password) => post("/api/auth/login", { email, password }),
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
  typing: (id) => post(`/api/tickets/${id}/typing`),
  callbacks: (id) => request(`/api/tickets/${id}/callbacks`),
  requestCallback: (id, payload) => post(`/api/tickets/${id}/callbacks`, payload),
  updateCallback: (id, cbId, status) => patch(`/api/tickets/${id}/callbacks/${cbId}`, { status }),

  // admin tools
  kbMatch: (text) => post("/api/kb/test-match", { text }),
  whatIf: (payload) => post("/api/whatif", payload),
  rescore: () => post("/api/admin/rescore"),
};
