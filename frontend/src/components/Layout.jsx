import { Suspense, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, Bell, ChevronRight, FileSearch, Globe, LayoutDashboard, ListChecks, Menu, Monitor, Moon, Search, Settings2, ShieldCheck, Sun } from 'lucide-react'
import { api } from '../api/endpoints'
import { USE_MOCK } from '../api/client'
import { ROLES, useAuth } from '../auth/AuthContext'
import { useTheme } from '../theme/ThemeContext'
import { Segmented, Select, Skeleton, cx } from './ui'

const NAV = [
  { group: 'Monitor', items: [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
    { to: '/sites', label: 'Monitored websites', icon: Globe },
  ] },
  { group: 'Review', items: [
    { to: '/queue', label: 'Investigation queue', icon: ListChecks, badge: true },
    { to: '/claims', label: 'Claims', icon: FileSearch },
  ] },
  { group: 'Knowledge', items: [{ to: '/library', label: 'Medical library', icon: BookOpen }] },
  { group: 'Workspace', items: [{ to: '/admin', label: 'Administration', icon: Settings2, perm: 'administer' }] },
]
const TITLES = { sites: 'Monitored websites', queue: 'Investigation queue', claims: 'Claims', incidents: 'Incident', library: 'Medical library', admin: 'Administration' }

export default function Layout() {
  const [open, setOpen] = useState(false)
  const { user, role, setRole, can } = useAuth()
  const { mode, setMode, dark } = useTheme()
  const { pathname } = useLocation()
  const nav = useNavigate()
  const analytics = useQuery({ queryKey: ['analytics'], queryFn: api.analytics })
  const openCount = analytics.data?.kpis?.find((k) => k.key === 'open')?.value
  const seg = pathname.split('/').filter(Boolean)

  const search = (e) => {
    e.preventDefault()
    const q = new FormData(e.currentTarget).get('q').toString().trim()
    nav(q ? `/queue?status=all&q=${encodeURIComponent(q)}` : '/queue')
  }

  return (
    <div className="flex min-h-screen gap-3 p-3">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-lg focus:bg-ink focus:px-3 focus:py-2 focus:text-sm focus:text-on-ink">Skip to content</a>
      {open && <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
      <aside
        className={cx(
          'w-[248px] shrink-0 flex-col rounded-2xl border border-line bg-surface p-3',
          open ? 'fixed inset-y-3 left-3 z-40 flex shadow-xl' : 'hidden lg:sticky lg:top-3 lg:flex lg:h-[calc(100vh-24px)]'
        )}
      >
        <Link to="/" className="flex items-center gap-2.5 px-2 pb-4 pt-2" onClick={() => setOpen(false)}>
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-on-brand"><ShieldCheck size={19} /></span>
          <span className="font-display text-lg font-bold tracking-tight">MedGuard AI</span>
        </Link>
        <nav className="flex-1 space-y-5 overflow-y-auto">
          {NAV.map((g) => {
            const items = g.items.filter((i) => !i.perm || can(i.perm))
            if (!items.length) return null
            return (
              <div key={g.group}>
                <p className="px-3 pb-1.5 text-xs font-medium text-muted">{g.group}</p>
                {items.map(({ to, label, icon: Icon, end, badge }) => (
                  <NavLink
                    key={to} to={to} end={end} onClick={() => setOpen(false)}
                    className={({ isActive }) => cx('mb-0.5 flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-colors', isActive ? 'bg-ink font-medium text-on-ink' : 'text-ink/80 hover:bg-ink/5')}
                  >
                    <Icon size={17} />
                    <span className="flex-1">{label}</span>
                    {badge && openCount != null && <span className="rounded-full bg-blush px-2 py-0.5 text-[11px] font-semibold text-ink">{openCount}</span>}
                  </NavLink>
                ))}
              </div>
            )
          })}
        </nav>
        <div className="mt-3 rounded-xl bg-canvas/70 p-3">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-brand text-sm font-bold text-on-brand">{user.name.replace('Dr. ', '')[0]}</span>
            <div className="min-w-0"><p className="truncate text-sm font-medium">{user.name}</p><p className="truncate text-xs text-muted">{user.roleLabel}</p></div>
          </div>
          {USE_MOCK && (
            <div className="mt-3">
              <p id="role-label" className="mb-1 text-xs text-muted">Preview as role</p>
              <Select ariaLabel="Preview as role" value={role} onChange={setRole} options={Object.entries(ROLES).map(([k, v]) => ({ value: k, label: v.label }))} className="py-1.5" />
            </div>
          )}
          <div className="mt-3 flex items-center justify-between gap-2">
            <p className="text-xs text-muted">Appearance</p>
            <Segmented
              size="sm" label="Appearance" value={mode} onChange={setMode}
              options={[{ value: 'light', label: 'Light', icon: Sun }, { value: 'system', label: 'Match system', icon: Monitor }, { value: 'dark', label: 'Dark', icon: Moon }]}
            />
          </div>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        {USE_MOCK && <div className="mb-4 rounded-xl bg-butter px-4 py-2 text-sm text-ink">Mock mode: you are looking at sample data. Set <code className="font-mono text-xs">VITE_USE_MOCK=false</code> to use the live API.</div>}
        <header className="mb-5 flex items-center gap-3 px-1 py-1">
          <button className="rounded-xl border border-line bg-surface p-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={18} /></button>
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm">
            <Link to="/" className="text-muted hover:text-ink">Home</Link>
            {seg.map((s, i) => (
              <span key={i} className="flex items-center gap-1.5">
                <ChevronRight size={14} className="text-muted" />
                <span className={i === seg.length - 1 ? 'font-medium' : 'text-muted'}>{i === 0 ? TITLES[s] ?? s : s}</span>
              </span>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <form onSubmit={search} role="search" className="relative hidden md:block">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input name="q" placeholder="Search findings, claims, sites" aria-label="Search findings" className="w-72 rounded-xl border border-line bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15" />
            </form>
            <button type="button" onClick={() => setMode(dark ? 'light' : 'dark')} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} title={dark ? 'Light mode' : 'Dark mode'} className="rounded-xl border border-line bg-surface p-2 transition-colors hover:bg-hover">
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <Link to="/queue" className="relative rounded-xl border border-line bg-surface p-2" aria-label="Open the queue">
              <Bell size={17} />
              {openCount > 0 && <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-red-500 ring-2 ring-surface" />}
            </Link>
          </div>
        </header>
        <main id="main" className="pb-10">
          <Suspense fallback={<div className="space-y-4"><Skeleton className="h-10 w-1/3" /><Skeleton className="h-64" /></div>}><Outlet /></Suspense>
        </main>
      </div>
    </div>
  )
}
