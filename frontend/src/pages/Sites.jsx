import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle2, Globe, Loader2, Plus, ScanLine } from 'lucide-react'
import { api } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { Banner, Button, Card, CardHead, Empty, ErrorState, Field, Modal, PageHeader, Pill, Select, Skeleton, Toggle, cx, inputCls, useToast } from '../components/ui'
import { fmtDateTime, timeAgo } from '../lib/format'

const INTERVALS = [[6, 'Every 6 hours'], [12, 'Every 12 hours'], [24, 'Daily'], [48, 'Every 2 days'], [168, 'Weekly']]
const intervalLabel = (h) => INTERVALS.find(([v]) => v === h)?.[1] ?? `Every ${h}h`

function ScanBanner({ id, domain, onClose }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['scan', id], queryFn: () => api.scan(id), refetchInterval: (query) => (query.state.data?.status === 'running' ? 1000 : false) })
  const s = q.data
  useEffect(() => {
    if (s && s.status !== 'running') ['sites', 'scans', 'analytics', 'incidents'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }))
  }, [s?.status]) // eslint-disable-line
  if (!s) return null
  const pct = Math.round((s.pages_done / Math.max(1, s.pages_total)) * 100)
  const done = s.status !== 'running'
  return (
    <Banner tone={done ? (s.status === 'failed' ? 'red' : 'green') : 'blue'} onClose={done ? onClose : undefined}>
      <div className="flex items-center gap-2 font-medium">
        {done ? <CheckCircle2 size={16} /> : <Loader2 size={16} className="animate-spin" />}
        {done ? `Scan of ${domain} ${s.status === 'failed' ? 'failed' : 'finished'}` : `Scanning ${domain}`}
      </div>
      <p className="mt-1 text-xs">{s.pages_done} of {s.pages_total} pages checked, {s.changed} changed, {s.claims_extracted} claims extracted</p>
      {!done && <div className="mt-2 h-1.5 rounded-full bg-surface/70"><div className="h-1.5 rounded-full bg-sky-500 transition-all" style={{ width: `${pct}%` }} /></div>}
    </Banner>
  )
}

function AddSite({ onClose }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [f, setF] = useState({ domain: '', jurisdiction: 'US', scan_interval_hours: 24 })
  const [err, setErr] = useState('')
  const m = useMutation({ mutationFn: api.addSite, onSuccess: (s) => { qc.invalidateQueries({ queryKey: ['sites'] }); toast(`Added ${s.domain}`); onClose() }, onError: (e) => setErr(e.message) })
  const submit = (e) => {
    e.preventDefault()
    const d = f.domain.trim().toLowerCase()
    if (!/^(?!-)[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(d)) return setErr('Enter a domain without http:// or a path, for example clinic.example.com')
    setErr('')
    m.mutate({ ...f, domain: d })
  }
  return (
    <Modal title="Add a website" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Domain" hint="Only approved public healthcare sites can be monitored. MedGuard follows robots.txt and rate limits.">
          <input autoFocus className={inputCls} placeholder="clinic.example.com" value={f.domain} onChange={(e) => setF({ ...f, domain: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Jurisdiction"><Select ariaLabel="Jurisdiction" value={f.jurisdiction} onChange={(v) => setF({ ...f, jurisdiction: v })} options={[{ value: 'US', label: 'United States' }]} /></Field>
          <Field label="Check"><Select ariaLabel="Check" value={f.scan_interval_hours} onChange={(v) => setF({ ...f, scan_interval_hours: v })} options={INTERVALS.map(([v, l]) => ({ value: v, label: l }))} /></Field>
        </div>
        {err && <p className="text-sm text-red-700 dark:text-red-300" role="alert">{err}</p>}
        <div className="flex justify-end gap-2 pt-1"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button variant="brand" disabled={m.isPending}>{m.isPending ? 'Adding…' : 'Add website'}</Button></div>
      </form>
    </Modal>
  )
}

export default function Sites() {
  const { can } = useAuth()
  const qc = useQueryClient()
  const sites = useQuery({ queryKey: ['sites'], queryFn: api.sites })
  const [sel, setSel] = useState(null)
  const [adding, setAdding] = useState(false)
  const [scan, setScan] = useState(null)
  const selected = sites.data?.find((s) => s.id === sel) ?? sites.data?.[0]
  const history = useQuery({ queryKey: ['scans', selected?.id], queryFn: () => api.scans({ site_id: selected.id }), enabled: !!selected })
  const start = useMutation({ mutationFn: (s) => api.startScan({ site_id: s.id }), onSuccess: (sc, s) => setScan({ id: sc.id, domain: s.domain }) })
  const toast = useToast()
  const toggle = useMutation({
    mutationFn: ({ id, enabled }) => api.updateSite(id, { enabled }),
    // Flip the switch immediately; roll back if the server rejects it.
    onMutate: async ({ id, enabled }) => {
      await qc.cancelQueries({ queryKey: ['sites'] })
      const prev = qc.getQueryData(['sites'])
      qc.setQueryData(['sites'], (l) => l?.map((s) => (s.id === id ? { ...s, enabled } : s)))
      return { prev }
    },
    onError: (e, _v, ctx) => { qc.setQueryData(['sites'], ctx?.prev); toast(e.message || 'Could not update the website', 'red') },
    onSettled: () => qc.invalidateQueries({ queryKey: ['sites'] }),
  })

  return (
    <>
      <PageHeader title="Monitored websites" subtitle="Approved sites that MedGuard checks for out-of-date or conflicting medical claims.">
        {can('manageSites') && <Button variant="brand" onClick={() => setAdding(true)}><Plus size={16} />Add website</Button>}
      </PageHeader>
      {scan && <ScanBanner {...scan} onClose={() => setScan(null)} />}
      {start.error && <Banner tone="red">{start.error.message}</Banner>}

      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <Card className="overflow-hidden">
          {sites.isLoading ? <div className="space-y-2 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
            : sites.error ? <ErrorState error={sites.error} onRetry={sites.refetch} />
            : !sites.data.length ? <Empty title="No websites yet" hint="Add the first site to start monitoring." />
            : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-line text-xs text-muted"><tr>{['Website', 'Pages', 'Check', 'Last scan', 'Active', ''].map((h) => <th key={h} className="px-5 py-3 font-medium">{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-line">
                    {sites.data.map((s) => (
                      <tr key={s.id} onClick={() => setSel(s.id)} className={cx('cursor-pointer transition-colors hover:bg-hover', selected?.id === s.id && 'bg-brand-soft/50')}>
                        <td className="px-5 py-3.5"><div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-canvas"><Globe size={16} /></span><div><p className="font-medium">{s.domain}</p><p className="text-xs text-muted">{s.jurisdiction} · {s.language.toUpperCase()}</p></div></div></td>
                        <td className="px-5 py-3.5">{s.pages}</td>
                        <td className="px-5 py-3.5 text-muted">{intervalLabel(s.scan_interval_hours)}</td>
                        <td className="px-5 py-3.5">{s.last_scan_at ? <div><p>{timeAgo(s.last_scan_at)}</p>{s.last_scan_status === 'failed' && <Pill tone="red" className="mt-1">Failed</Pill>}</div> : <span className="text-muted">Never</span>}</td>
                        <td className="px-5 py-3.5" onClick={(e) => e.stopPropagation()}><Toggle label={`Monitor ${s.domain}`} checked={s.enabled} disabled={!can('manageSites')} onChange={(enabled) => toggle.mutate({ id: s.id, enabled })} /></td>
                        <td className="px-5 py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                          {can('scan') && <Button size="sm" variant="outline" disabled={!s.enabled || start.isPending || scan} onClick={() => start.mutate(s)}><ScanLine size={14} />Scan now</Button>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </Card>

        <Card>
          <CardHead title={selected ? `Crawl history` : 'Crawl history'} hint={selected?.domain} />
          {!selected ? <Empty title="Select a website" /> : history.isLoading ? <div className="space-y-2 p-5"><Skeleton className="h-14" /><Skeleton className="h-14" /></div>
            : history.error ? <ErrorState error={history.error} onRetry={history.refetch} />
            : (
              <ul className="divide-y divide-line">
                {history.data.map((h) => (
                  <li key={h.id} className="px-5 py-3">
                    <div className="flex items-center justify-between"><p className="text-sm font-medium">{fmtDateTime(h.started_at)}</p><Pill tone={h.status === 'failed' ? 'red' : h.status === 'running' ? 'blue' : 'green'}>{h.status === 'failed' ? 'Failed' : h.status === 'running' ? 'Running' : 'Completed'}</Pill></div>
                    <p className="mt-0.5 text-xs text-muted">{h.status === 'failed' ? h.error : `${h.pages_total} pages, ${h.changed} changed, ${h.claims_extracted} claims`} · {h.trigger}</p>
                  </li>
                ))}
              </ul>
            )}
        </Card>
      </div>
      {adding && <AddSite onClose={() => setAdding(false)} />}
    </>
  )
}
