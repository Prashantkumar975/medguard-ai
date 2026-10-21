import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { USE_MOCK, clearTokens, loginRequest, logoutRequest, meRequest, getToken, getRefresh } from '../api/client'

// Role labels + permission map (mirrors the backend ROLE_PERMS in app/api/deps.py).
export const ROLES = {
  admin: { label: 'Administrator', name: 'Administrator' },
  reviewer: { label: 'Clinical reviewer', name: 'Clinical reviewer' },
  viewer: { label: 'Viewer', name: 'Viewer' },
}
const PERMS = {
  review: ['admin', 'reviewer'],
  scan: ['admin', 'reviewer'],
  manageSites: ['admin'],
  administer: ['admin'],
}

const Ctx = createContext(null)

export function AuthProvider({ children }) {
  const [role, setRoleState] = useState(() => (USE_MOCK ? localStorage.getItem('mg_role') || 'reviewer' : null))
  const [user, setUser] = useState(null) // live-mode account from GET /auth/me
  const [loading, setLoading] = useState(!USE_MOCK)
  const [error, setError] = useState(null)

  // On mount in live mode, restore the session from stored credentials. If only
  // the refresh token survives (access token lost/expired), meRequest still
  // recovers the session through its refresh path — don't bail out early.
  useEffect(() => {
    if (USE_MOCK) return
    if (!getToken() && !getRefresh()) {
      setLoading(false)
      return
    }
    let alive = true
    meRequest()
      .then((me) => {
        if (!alive) return
        setUser(me)
        setRoleState(me.role)
      })
      .catch(() => {
        if (alive) clearTokens()
      })
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [])

  const login = async (email, password) => {
    setError(null)
    await loginRequest(email, password)
    const me = await meRequest()
    setUser(me)
    setRoleState(me.role)
    return me
  }

  const logout = async () => {
    if (!USE_MOCK) await logoutRequest().catch(() => {})
    setUser(null)
    setRoleState(null)
  }

  const setRole = (r) => {
    // Preview-as-role is a mock-only affordance; live mode derives role from the server.
    if (!USE_MOCK) return
    localStorage.setItem('mg_role', r)
    setRoleState(r)
  }

  const value = useMemo(() => {
    const effectiveRole = role || 'viewer'
    const label = ROLES[effectiveRole]?.label || effectiveRole
    const name = user?.name || (USE_MOCK ? ROLES[effectiveRole]?.name : '') || label
    return {
      role: effectiveRole,
      user: { name, roleLabel: label, email: user?.email, id: user?.id },
      isAuthenticated: USE_MOCK ? true : !!user,
      loading,
      error,
      login,
      logout,
      can: (action) => (PERMS[action]?.includes(effectiveRole) ?? false),
      setRole,
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, user, loading, error])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
