import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/endpoints'
import { useAuth, ROLES } from '../auth/AuthContext'
import { Banner, Button, Card, CardHead, Empty, ErrorState, Field, PageHeader, Select, Skeleton, cx, inputCls, useToast } from '../components/ui'
import { timeAgo } from '../lib/format'

function Users() {
  const qc = useQueryClient()
  const toast = useToast()
  const u = useQuery({ queryKey: ['users'], queryFn: api.users })
  const m = useMutation({ mutationFn: ({ id, role }) => api.updateUser(id, { role }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); toast('Role updated') } })
  if (u.isLoading) return <Skeleton className="m-5 h-40" />
  if (u.error) return <ErrorState error={u.error} onRetry={u.refetch} />
  return (
    <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead className="border-b border-line text-xs text-muted"><tr>{['Person', 'Role', 'Last active'].map((h) => <th key={h} className="px-5 py-3 font-medium">{h}</th>)}</tr></thead>
      <tbody className="divide-y divide-line">
        {u.data.map((x) => (
          <tr key={x.id}>
            <td className="px-5 py-3.5"><p className="font-medium">{x.name}</p><p className="text-xs text-muted">{x.email}</p></td>
            <td className="px-5 py-3.5"><Select ariaLabel={`Role for ${x.name}`} block={false} className="min-w-44" value={x.role} disabled={m.isPending} onChange={(v) => m.mutate({ id: x.id, role: v })} options={Object.entries(ROLES).map(([k, v]) => ({ value: k, label: v.label }))} /></td>
            <td className="px-5 py-3.5 text-muted">{timeAgo(x.last_active)}</td>
          </tr>
        ))}
      </tbody>
    </table></div>
  )
}

function SettingsForm({ section }) {
  const qc = useQueryClient()
  const toast = useToast()
  const s = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const [f, setF] = useState(null)
  const [saved, setSaved] = useState(false)
  useEffect(() => { if (s.data) setF(s.data[section]) }, [s.data, section])
  const m = useMutation({ mutationFn: () => api.saveSettings({ ...s.data, [section]: f }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['settings'] }); setSaved(true); toast('Settings saved') } })
  if (s.error) return <ErrorState error={s.error} onRetry={s.refetch} />
  if (!f) return <Skeleton className="m-5 h-40" />
  const set = (k, v) => { setSaved(false); setF({ ...f, [k]: v }) }

  return (
    <form onSubmit={(e) => { e.preventDefault(); m.mutate() }} className="max-w-xl space-y-5 p-5">
      {section === 'notifications' ? (
        <>
          <Field label="Minimum priority for in-app notifications" hint="Lower priority findings remain in the incident queue but do not create a notification."><Select ariaLabel="Minimum priority for in-app notifications" value={f.min_priority} onChange={(v) => set('min_priority', v)} options={Object.entries({ critical: { label: 'Critical' }, high: { label: 'High' }, medium: { label: 'Medium' }, low: { label: 'Low' } }).map(([k, v]) => ({ value: k, label: `${v.label} and above` }))} /></Field>
        </>
      ) : (
        <>
          <Field label="Organization name"><input className={inputCls} value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
          <Field label="Default scan frequency"><Select ariaLabel="Default scan frequency" value={f.default_scan_interval_hours} onChange={(v) => set('default_scan_interval_hours', v)} options={[[6, 'Every 6 hours'], [12, 'Every 12 hours'], [24, 'Daily'], [168, 'Weekly']].map(([v, l]) => ({ value: v, label: l }))} /></Field>
          <Field label="Keep unreferenced page snapshots for" hint="In days. Findings, current page versions, and the audit trail are retained."><input type="number" min="30" max="3650" className={cx(inputCls, 'no-spin')} value={f.retention_days} onChange={(e) => set('retention_days', Number(e.target.value))} /></Field>
          <Field label="Jurisdictions" hint="Only the United States is available in this release."><input className={inputCls} value={f.jurisdictions.join(', ')} disabled /></Field>
        </>
      )}
      {m.error && <Banner tone="red">{m.error.message}</Banner>}
      <Button variant="brand" disabled={m.isPending}>{m.isPending ? 'Saving…' : 'Save changes'}</Button>
    </form>
  )
}

const TABS = [['users', 'People and roles'], ['notifications', 'Notifications'], ['organization', 'Organization']]

export default function Admin() {
  const { can } = useAuth()
  const [tab, setTab] = useState('users')
  if (!can('administer')) return <Card><Empty title="Administrators only" hint="Ask an administrator if you need access to roles or settings." /></Card>
  return (
    <>
      <PageHeader title="Administration" subtitle="Manage who can review findings, how alerts are sent and organization defaults." />
      <Card>
        <div className="flex gap-1 border-b border-line px-3 pt-2" role="tablist">
          {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={cx('-mb-px border-b-2 px-3 py-2.5 text-sm transition-colors', tab === k ? 'border-brand font-medium' : 'border-transparent text-muted hover:text-ink')}>{l}</button>)}
        </div>
        {tab === 'users' ? <Users /> : <SettingsForm key={tab} section={tab} />}
      </Card>
    </>
  )
}
