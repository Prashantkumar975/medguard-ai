import { createContext, useContext, useEffect, useMemo, useState } from 'react'

const KEY = 'mg_theme'
const Ctx = createContext({ mode: 'system', dark: false, setMode: () => {} })

const systemDark = () => window.matchMedia('(prefers-color-scheme: dark)').matches

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(() => localStorage.getItem(KEY) || 'system')
  const [sys, setSys] = useState(systemDark)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const h = (e) => setSys(e.matches)
    mq.addEventListener('change', h)
    return () => mq.removeEventListener('change', h)
  }, [])

  const dark = mode === 'dark' || (mode === 'system' && sys)
  useEffect(() => { document.documentElement.classList.toggle('dark', dark) }, [dark])

  const value = useMemo(() => ({
    mode, dark,
    setMode: (m) => { localStorage.setItem(KEY, m); setModeState(m) },
  }), [mode, dark])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
export const useTheme = () => useContext(Ctx)
