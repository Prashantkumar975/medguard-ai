import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { request, USE_MOCK } from '../api/client'

export const ROLES = {
  admin: { label: 'Administrator', name: 'Sam Okafor' },
  reviewer: { label: 'Clinical reviewer', name: 'Dr. Maya Rao' },
  viewer: { label: 'Viewer', name: 'Lee Chen' },
}
const PERMS = {
  review: ['admin', 'reviewer'],
  scan: ['admin', 'reviewer'],
  manageSites: ['admin'],
  administer: ['admin'],
}

const Ctx = createContext(null)
const initialRole = () => {
  const stored = localStorage.getItem('mg_role')
  return ROLES[stored] ? stored : 'reviewer'
}

export function AuthProvider({ children }) {
  const [role, setRoleState] = useState(initialRole)
  const [user, setUser] = useState(() => ({ ...ROLES[initialRole()] }))
  const [isAuthenticated, setAuthenticated] = useState(() => (
    USE_MOCK ? localStorage.getItem('mg_demo_authenticated') === '1' : Boolean(localStorage.getItem('mg_token'))
  ))
  const [loading, setLoading] = useState(() => !USE_MOCK && Boolean(localStorage.getItem('mg_token')))

  useEffect(() => {
    if (USE_MOCK || !localStorage.getItem('mg_token')) return
    request('GET', '/auth/me')
      .then((account) => {
        setRoleState(account.role)
        localStorage.setItem('mg_role', account.role)
        setUser({
          name: account.name,
          email: account.email,
          organizationId: account.organization_id,
          roleLabel: ROLES[account.role]?.label || account.role,
        })
        setAuthenticated(true)
      })
      .catch(() => {
        localStorage.removeItem('mg_token')
        localStorage.removeItem('mg_refresh_token')
        setAuthenticated(false)
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const expireSession = () => setAuthenticated(false)
    window.addEventListener('medguard:auth-expired', expireSession)
    return () => window.removeEventListener('medguard:auth-expired', expireSession)
  }, [])

  const login = async (email, password, organizationId = '') => {
    if (!email || !password) throw new Error('Enter your email and password')
    if (USE_MOCK) {
      const demoRole = 'reviewer'
      localStorage.setItem('mg_demo_authenticated', '1')
      localStorage.setItem('mg_role', demoRole)
      setRoleState(demoRole)
      setUser({ ...ROLES[demoRole] })
      setAuthenticated(true)
      return
    }

    const tokens = await request('POST', '/auth/login', {
      body: { email, password, ...(organizationId ? { organization_id: organizationId } : {}) },
    })
    localStorage.setItem('mg_token', tokens.access_token)
    localStorage.setItem('mg_refresh_token', tokens.refresh_token)
    try {
      const account = await request('GET', '/auth/me')
      setRoleState(account.role)
      localStorage.setItem('mg_role', account.role)
      setUser({
        name: account.name,
        email: account.email,
        organizationId: account.organization_id,
        roleLabel: ROLES[account.role]?.label || account.role,
      })
      setAuthenticated(true)
    } catch (error) {
      localStorage.removeItem('mg_token')
      localStorage.removeItem('mg_refresh_token')
      throw error
    }
  }

  const register = async ({ name, email, organizationName, password }) => {
    if (USE_MOCK) throw new Error('Registration requires the live API. Disable demo mode and start the backend.')
    const tokens = await request('POST', '/auth/register', {
      body: { name, email, organization_name: organizationName, password },
    })
    localStorage.setItem('mg_token', tokens.access_token)
    localStorage.setItem('mg_refresh_token', tokens.refresh_token)
    try {
      const account = await request('GET', '/auth/me')
      setRoleState(account.role)
      localStorage.setItem('mg_role', account.role)
      setUser({
        name: account.name,
        email: account.email,
        organizationId: account.organization_id,
        roleLabel: ROLES[account.role]?.label || account.role,
      })
      setAuthenticated(true)
    } catch (error) {
      localStorage.removeItem('mg_token')
      localStorage.removeItem('mg_refresh_token')
      throw error
    }
  }

  const logout = async () => {
    const refreshToken = localStorage.getItem('mg_refresh_token')
    if (!USE_MOCK && refreshToken) {
      try {
        await request('POST', '/auth/logout', { body: { refresh_token: refreshToken } })
      } catch {
        // Clear the browser session even if the API cannot be reached.
      }
    }
    localStorage.removeItem('mg_token')
    localStorage.removeItem('mg_refresh_token')
    localStorage.removeItem('mg_demo_authenticated')
    setAuthenticated(false)
  }

  const setRole = (nextRole) => {
    if (!ROLES[nextRole]) return
    localStorage.setItem('mg_role', nextRole)
    setRoleState(nextRole)
    if (USE_MOCK) setUser({ ...ROLES[nextRole] })
  }

  const value = useMemo(() => ({
    role,
    user,
    loading,
    isAuthenticated,
    login,
    register,
    logout,
    can: (action) => PERMS[action]?.includes(role) ?? false,
    setRole,
  }), [role, user, loading, isAuthenticated])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
