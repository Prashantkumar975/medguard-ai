// One place that talks to the backend. Flip VITE_USE_MOCK in .env to switch.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
const BASE = import.meta.env.VITE_API_URL || ''

// --- token storage (live mode only) ---
export const getToken = () => localStorage.getItem('mg_token')
export const getRefresh = () => localStorage.getItem('mg_refresh')
export function setTokens({ access_token, refresh_token }) {
  if (access_token) localStorage.setItem('mg_token', access_token)
  if (refresh_token) localStorage.setItem('mg_refresh', refresh_token)
}
export function clearTokens() {
  localStorage.removeItem('mg_token')
  localStorage.removeItem('mg_refresh')
}

async function rawFetch(method, path, { params, body, token } = {}) {
  const clean = Object.entries(params || {}).filter(([, v]) => v !== '' && v != null)
  const qs = clean.length ? `?${new URLSearchParams(clean)}` : ''
  return fetch(`${BASE}/api/v1${path}${qs}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
}

// Single-flight refresh: concurrent 401s (StrictMode double-mount, parallel
// queries) must share ONE refresh request. Two parallel refreshes with the same
// token race the server's rotation — the loser presents a token the server just
// revoked, fails, and would clearTokens() the winner's fresh pair, silently
// destroying an otherwise healthy session.
let refreshInFlight = null

async function tryRefresh() {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    const refresh_token = getRefresh()
    if (!refresh_token) return false
    try {
      const res = await fetch(`${BASE}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token }),
      })
      if (!res.ok) {
        clearTokens()
        return false
      }
      setTokens(await res.json())
      return true
    } catch {
      return false // network hiccup — keep existing tokens, don't log the user out
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

export async function request(method, path, { params, body } = {}) {
  if (USE_MOCK) {
    const { mockRequest } = await import('./mock')
    return mockRequest(method, path, params, body)
  }
  let res = await rawFetch(method, path, { params, body, token: getToken() })
  // One transparent retry after a refresh when the access token has expired.
  if (res.status === 401 && getToken()) {
    if (await tryRefresh()) {
      res = await rawFetch(method, path, { params, body, token: getToken() })
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(typeof err.detail === 'string' ? err.detail : `Request failed (${res.status})`)
  }
  return res.status === 204 ? null : res.json()
}

// --- explicit auth calls (live mode) ---
export async function loginRequest(email, password) {
  const res = await rawFetch('POST', '/auth/login', { body: { email, password } })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Login failed')
  }
  const pair = await res.json()
  setTokens(pair)
  return pair
}

export async function meRequest() {
  const res = await rawFetch('GET', '/auth/me', { token: getToken() })
  if (res.status === 401) {
    if (await tryRefresh()) {
      const retry = await rawFetch('GET', '/auth/me', { token: getToken() })
      if (retry.ok) return retry.json()
    }
    throw new Error('Not authenticated')
  }
  if (!res.ok) throw new Error('Could not load account')
  return res.json()
}

export async function logoutRequest() {
  const refresh_token = getRefresh()
  if (refresh_token) {
    await rawFetch('POST', '/auth/logout', { body: { refresh_token } }).catch(() => {})
  }
  clearTokens()
}
