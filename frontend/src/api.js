const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail = Array.isArray(body.detail)
          ? body.detail.map((d) => d.msg).join("; ")
          : String(body.detail);
      }
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body ?? {}) });

export const api = {
  health: () => request("/api/health"),
  config: () => request("/api/config"),
  customers: () => request("/api/customers"),
  tickets: () => request("/api/tickets"),
  stats: () => request("/api/stats"),
  simulation: () => request("/api/simulation"),
  submitTicket: (payload) => post("/api/tickets", payload),
  override: (id, payload) => post(`/api/tickets/${id}/override`, payload),
  resolve: (id) => post(`/api/tickets/${id}/resolve`),
  feedback: (id, payload) => post(`/api/tickets/${id}/feedback`, payload),
  kbMatch: (text) => post("/api/kb/test-match", { text }),
  rescore: () => post("/api/admin/rescore"),
};
