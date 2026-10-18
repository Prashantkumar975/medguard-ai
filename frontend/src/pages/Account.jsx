import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Keyboard, LogOut, Monitor, Moon, Sun } from 'lucide-react'
import { api } from '../api/endpoints'
import { USE_MOCK } from '../api/client'
import { ROLES, useAuth } from '../auth/AuthContext'
import { useTheme } from '../theme/ThemeContext'
import { Button, Card, CardHead, PageHeader, Pill, Segmented, cx, useToast } from '../components/ui'
import { fmtDateTime, timeAgo } from '../lib/format'

const SHORTCUTS = [['/', 'Focus the header search'], ['Esc', 'Leave the search field'], ['Enter', 'Open the focused queue row']]

export default function Account() {
  const { role, setRole, user } = useAuth()
  const { mode, setMode, dark } = useTheme()
  const toast = useToast()
  const nav = useNavigate()

  // Profile details come from the same user list Administration edits.
  const users = useQuery({ queryKey: ['users'], queryFn: api.users, enabled: USE_MOCK })
  const me = users.data?.find((u) => u.role === role) ?? users.data?.find((u) => u.name === user.name)

  const initials = user.name.replace('Dr. ', '').split(' ').map((w) => w[0]).join('').slice(0, 2)

  return (
    <>
      <PageHeader title="Account" subtitle="Your profile, appearance and session. Manage team members and workspace settings in Administration." />

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        {/* Profile */}
        <Card>
          <CardHead title="Profile" />
          <div className="px-5 pb-5">
            <div className="flex items-center gap-4">
              <span className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-brand text-lg font-bold text-on-brand">{initials}</span>
              <div className="min-w-0">
                <p className="font-display text-lg font-bold">{user.name}</p>
                <p className="text-sm text-muted">{me?.email ?? '—'}</p>
              </div>
              <Pill tone="violet" className="ml-auto">{user.roleLabel}</Pill>
            </div>
            <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-line pt-4 text-sm">
              <div>
                <dt className="text-xs text-muted">Email</dt>
                <dd className="mt-0.5">{me?.email ?? 'Not available'}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Last active</dt>
                <dd className="mt-0.5">{me ? `${fmtDateTime(me.last_active)} (${timeAgo(me.last_active)})` : '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Workspace role</dt>
                <dd className="mt-0.5">{user.roleLabel}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Jurisdiction</dt>
                <dd className="mt-0.5">United States</dd>
              </div>
            </dl>
            <p className="mt-4 text-xs text-muted">Profile changes and password resets are managed by your administrator in Administration → People.</p>
          </div>
        </Card>

        <div className="space-y-4">
          {/* Appearance */}
          <Card>
            <CardHead title="Appearance" hint="Applies to this device only" />
            <div className="flex items-center justify-between gap-4 px-5 pb-5">
              <div className="flex items-center gap-2 text-sm">
                {dark ? <Moon size={16} aria-hidden="true" /> : <Monitor size={16} aria-hidden="true" />}
                Theme
              </div>
              <Segmented
                label="Theme" value={mode} onChange={setMode}
                options={[{ value: 'light', label: 'Light', icon: Sun }, { value: 'system', label: 'Match system', icon: Monitor }, { value: 'dark', label: 'Dark', icon: Moon }]}
              />
            </div>
          </Card>

          {/* Session */}
          <Card>
            <CardHead title="Session" hint={USE_MOCK ? 'Mock mode — roles are simulated locally' : 'Connected to the live API'} />
            <div className="space-y-4 px-5 pb-5">
              {USE_MOCK ? (
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium">Preview as role</p>
                    <p className="text-xs text-muted">Switch the simulated role to check what each one can see.</p>
                  </div>
                  <Segmented
                    label="Preview as role" value={role} onChange={setRole}
                    options={Object.entries(ROLES).map(([k, v]) => ({ value: k, label: v.label, text: v.label.split(' ')[0] }))}
                  />
                </div>
              ) : (
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium">Signed in as {user.name}</p>
                    <p className="text-xs text-muted">Role changes are made by an administrator.</p>
                  </div>
                  <Button variant="outline" onClick={() => { localStorage.removeItem('mg_token'); toast('Signed out'); nav('/') }}><LogOut size={15} />Sign out</Button>
                </div>
              )}
            </div>
          </Card>

          {/* Shortcuts */}
          <Card>
            <CardHead title="Keyboard shortcuts" />
            <ul className="space-y-2.5 px-5 pb-5">
              {SHORTCUTS.map(([k, label]) => (
                <li key={k} className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2 text-muted"><Keyboard size={14} aria-hidden="true" />{label}</span>
                  <kbd className={cx('rounded-md border border-line bg-canvas px-2 py-0.5 font-mono text-xs')}>{k}</kbd>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  )
}
