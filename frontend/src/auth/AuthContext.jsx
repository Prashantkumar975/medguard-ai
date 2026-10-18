import { createContext, useContext, useMemo, useState } from 'react'

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

// TODO(backend): replace this with the real session, e.g. GET /me, and set localStorage "mg_token" after login.
export function AuthProvider({ children }) {
  const [role, setRoleState] = useState(() => localStorage.getItem('mg_role') || 'reviewer')
  const value = useMemo(
    () => ({
      role,
      user: { name: ROLES[role].name, roleLabel: ROLES[role].label },
      can: (action) => PERMS[action]?.includes(role) ?? false,
      setRole: (r) => { localStorage.setItem('mg_role', r); setRoleState(r) },
    }),
    [role]
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
export const useAuth = () => useContext(Ctx)
