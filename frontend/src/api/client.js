// One place that talks to the backend. Flip VITE_USE_MOCK in .env to switch.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
const BASE = import.meta.env.VITE_API_URL || ''

export async function request(method, path, { params, body } = {}) {
  if (USE_MOCK) {
    const { mockRequest } = await import('./mock')
    return mockRequest(method, path, params, body)
  }
  const clean = Object.entries(params || {}).filter(([, v]) => v !== '' && v != null)
  const qs = clean.length ? `?${new URLSearchParams(clean)}` : ''
  const token = localStorage.getItem('mg_token') // TODO(backend): set after login
  const res = await fetch(`${BASE}/api/v1${path}${qs}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Request failed (${res.status})`)
  }
  return res.status === 204 ? null : res.json()
}
