// Real API mode is the default. Set VITE_USE_MOCK=true only for the sample demo.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
let refreshPromise = null

function clearTokens() {
  localStorage.removeItem('mg_token')
  localStorage.removeItem('mg_refresh_token')
  window.dispatchEvent(new Event('medguard:auth-expired'))
}

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('mg_refresh_token')
  if (!refreshToken) {
    clearTokens()
    return null
  }
  if (!refreshPromise) {
    refreshPromise = fetch(`${BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).then(async (response) => {
      if (!response.ok) {
        clearTokens()
        return null
      }
      const tokens = await response.json()
      localStorage.setItem('mg_token', tokens.access_token)
      localStorage.setItem('mg_refresh_token', tokens.refresh_token)
      return tokens.access_token
    }).catch(() => {
      clearTokens()
      return null
    }).finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

export async function request(method, path, { params, body } = {}) {
  if (USE_MOCK) {
    const { mockRequest } = await import('./mock')
    return mockRequest(method, path, params, body)
  }
  const clean = Object.entries(params || {}).filter(([, v]) => v !== '' && v != null)
  const qs = clean.length ? `?${new URLSearchParams(clean)}` : ''
  const url = `${BASE}/api/v1${path}${qs}`
  const send = (token) => fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  let res = await send(localStorage.getItem('mg_token'))
  if (res.status === 401 && path !== '/auth/login' && path !== '/auth/refresh' && path !== '/auth/logout') {
    const token = await refreshAccessToken()
    if (token) res = await send(token)
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = Array.isArray(err.detail)
      ? err.detail.map((item) => item.msg).filter(Boolean).join('; ')
      : err.detail
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return res.status === 204 ? null : res.json()
}
