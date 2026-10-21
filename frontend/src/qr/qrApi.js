const API_BASE = String(import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export function qrApiUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

function authHeaders(json = false) {
  const token = localStorage.getItem("access_token") || localStorage.getItem("token");
  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function request(path, options = {}) {
  const response = await fetch(qrApiUrl(path), {
    ...options,
    headers: { ...authHeaders(Boolean(options.body)), ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) throw new Error("Your session has expired. Please sign in again.");
    throw new Error(data.detail || data.message || "Request failed. Please try again.");
  }
  return data;
}

export const qrApi = {
  resources: () => request("/api/qr-codes/resources"),
  list: () => request("/api/qr-codes"),
  create: (payload) => request("/api/qr-codes", { method: "POST", body: JSON.stringify(payload) }),
  update: (id, payload) => request(`/api/qr-codes/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  setStatus: (id, is_active) => request(`/api/qr-codes/${id}/status`, { method: "PATCH", body: JSON.stringify({ is_active }) }),
  remove: (id) => request(`/api/qr-codes/${id}`, { method: "DELETE" }),
  resolvePublic: (token) => request(`/api/public/qr/${encodeURIComponent(token)}`, { headers: {} }),
  track: (token, event_type, session_id) => request(`/api/public/qr/${encodeURIComponent(token)}/events`, {
    method: "POST", body: JSON.stringify({ event_type, session_id }), headers: {},
  }),
};
