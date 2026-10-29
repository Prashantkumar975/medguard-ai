import { Suspense, useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Activity, BookOpen, Bell, ChevronRight, CircleHelp, FileSearch, FileText, Globe, LayoutDashboard, ListChecks, LogOut, Menu, Monitor, Moon, ScrollText, Search, Settings2, ShieldCheck, Sun, UserRound, X } from 'lucide-react'
import { api } from '../api/endpoints'
import { USE_MOCK } from '../api/client'
import { ROLES, useAuth } from '../auth/AuthContext'
import { useTheme } from '../theme/ThemeContext'
import ErrorBoundary from './ErrorBoundary'
import { Segmented, Select, Skeleton, cx } from './ui'

const NAV = [
  { group: 'Monitor', items: [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
    { to: '/sites', label: 'Monitored websites', icon: Globe },
    { to: '/status', label: 'System status', icon: Activity },
  ] },
  { group: 'Review', items: [
    { to: '/queue', label: 'Investigation queue', icon: ListChecks, badge: 'queue' },
    { to: '/claims', label: 'Claims', icon: FileSearch },
    { to: '/notifications', label: 'Notifications', icon: Bell, badge: 'notifications' },
  ] },
  { group: 'Knowledge', items: [
    { to: '/library', label: 'Medical library', icon: BookOpen },
    { to: '/reports', label: 'Reports', icon: FileText },
    { to: '/audit', label: 'Audit log', icon: ScrollText },
  ] },
  { group: 'Workspace', items: [
    { to: '/account', label: 'Account', icon: UserRound },
    { to: '/help', label: 'Help & about', icon: CircleHelp },
    { to: '/admin', label: 'Administration', icon: Settings2, perm: 'administer' },
  ] },
]
const TITLES = { sites: 'Monitored websites', status: 'System status', queue: 'Investigation queue', claims: 'Claims', notifications: 'Notifications', incidents: 'Incident', library: 'Medical library', reports: 'Reports', audit: 'Audit log', account: 'Account', help: 'Help & about', admin: 'Administration' }

export default function Layout() {
  const [open, setOpen] = useState(false)
  const [mockDismissed, setMockDismissed] = useState(() => localStorage.getItem('mg_mock_dismissed') === '1')
  const searchRef = useRef(null)
  const { user, role, setRole, can, logout } = useAuth()
  const { mode, setMode, dark } = useTheme()
  const { pathname } = useLocation()
  const nav = useNavigate()

  // Start each new page at the top — otherwise navigating from a long page lands you mid-scroll.
  useEffect(() => { window.scrollTo({ top: 0 }) }, [pathname])

  // Press "/" anywhere (outside inputs) to jump to search; Escape leaves the field.
  useEffect(() => {
    const h = (e) => {
      const t = e.target
      const typing = t instanceof HTMLElement && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable || t.getAttribute?.('role') === 'combobox')
      if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault()
        searchRef.current?.focus()
      } else if (e.key === 'Escape' && document.activeElement === searchRef.current) {
        searchRef.current?.blur()
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])

  const dismissMock = () => {
    localStorage.setItem('mg_mock_dismissed', '1')
    setMockDismissed(true)
  }
  const signOut = async () => {
    await logout()
    nav('/login', { replace: true })
  }
  const analytics = useQuery({ queryKey: ['analytics'], queryFn: api.analytics })
  const openCount = analytics.data?.kpis?.find((k) => k.key === 'open')?.value
  const notifs = useQuery({ queryKey: ['notifications'], queryFn: api.notifications })
  const unread = notifs.data?.filter((n) => !n.read).length ?? 0
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
                {items.map(({ to, label, icon: Icon, end, badge }) => {
                  const count = badge === 'queue' ? openCount : badge === 'notifications' ? unread : null
                  return (
                    <NavLink
                      key={to} to={to} end={end} onClick={() => setOpen(false)}
                      className={({ isActive }) => cx('mb-0.5 flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-colors', isActive ? 'bg-ink font-medium text-on-ink' : 'text-ink/80 hover:bg-ink/5')}
                    >
                      <Icon size={17} />
                      <span className="flex-1">{label}</span>
                      {count > 0 && <span className="rounded-full bg-blush px-2 py-0.5 text-[11px] font-semibold text-ink">{count}</span>}
                    </NavLink>
                  )
                })}
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
          <button type="button" onClick={signOut} className="mt-3 flex w-full items-center gap-2 rounded-lg border-t border-line px-1 pt-3 text-left text-sm text-muted transition-colors hover:text-ink">
            <LogOut size={15} />
            <span>Log out</span>
          </button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        {USE_MOCK && !mockDismissed && (
          <div className="mb-4 flex items-start justify-between gap-3 rounded-xl bg-butter px-4 py-2 text-sm text-ink">
            <p>Mock mode: you are looking at sample data. Set <code className="font-mono text-xs">VITE_USE_MOCK=false</code> to use the live API.</p>
            <button type="button" onClick={dismissMock} aria-label="Dismiss mock mode notice" className="-mr-1 shrink-0 rounded-lg p-1 transition-colors hover:bg-ink/10">
              <X size={15} />
            </button>
          </div>
        )}
        <header className="mb-5 flex items-center gap-3 px-1 py-1">
          <button className="rounded-xl border border-line bg-surface p-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={18} /></button>
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm">
            <Link to="/" className="text-muted hover:text-ink">Home</Link>
            {seg.map((s, i) => (
              <span key={i} className="flex items-center gap-1.5">
                <ChevronRight size={14} className="text-muted" />
                <span className={i === seg.length - 1 ? 'font-medium' : 'text-muted'}>{i === 0 ? TITLES[s] ?? s : seg[0] === 'sites' && i === 1 ? 'Website' : s}</span>
              </span>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {USE_MOCK && mockDismissed && (
              <span className="hidden rounded-full bg-butter px-2.5 py-1 text-[11px] font-semibold text-butter-ink sm:inline-block" title="You dismissed the mock-mode notice. Sample data only.">Mock data</span>
            )}
            <form onSubmit={search} role="search" className="relative hidden md:block">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input ref={searchRef} name="q" placeholder="Search findings, claims, sites" aria-label="Search findings" className="w-72 rounded-xl border border-line bg-surface py-2 pl-9 pr-8 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15" />
              <kbd aria-hidden="true" className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-line bg-canvas px-1.5 py-0.5 font-mono text-[10px] leading-none text-muted">/</kbd>
            </form>
            <button type="button" onClick={() => setMode(dark ? 'light' : 'dark')} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} title={dark ? 'Light mode' : 'Dark mode'} className="rounded-xl border border-line bg-surface p-2 transition-colors hover:bg-hover">
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <Link to="/notifications" className="relative rounded-xl border border-line bg-surface p-2 transition-colors hover:bg-hover" aria-label={unread ? `Notifications (${unread} unread)` : 'Notifications'}>
              <Bell size={17} />
              {unread > 0 && <span className="absolute -right-1 -top-1 grid min-w-[17px] place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white ring-2 ring-surface">{unread}</span>}
            </Link>
          </div>
        </header>
        <main id="main" className="pb-10">
          <div key={pathname} className="mg-fade">
            <ErrorBoundary>
              <Suspense fallback={<div className="space-y-4"><Skeleton className="h-10 w-1/3" /><Skeleton className="h-64" /></div>}><Outlet /></Suspense>
            </ErrorBoundary>
          </div>
        </main>
        <footer className="border-t border-line px-1 py-5 text-xs text-muted">
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
            <p className="max-w-prose leading-relaxed">
              <span className="font-medium text-ink">MedGuard AI</span> flags potential discrepancies for human review. It does not provide medical advice — a qualified clinician approves every correction.
            </p>
            <nav aria-label="Project information" className="flex items-center gap-4">
              <a href="/help" className="transition-colors hover:text-ink">Evidence and limitations</a>
              <span>v{__PKG_VERSION__}</span>
            </nav>
          </div>
        </footer>
      </div>
    </div>
  )
}
