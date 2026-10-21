import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Search, ScrollText } from 'lucide-react'
import { api } from '../api/endpoints'
import { Card, Empty, ErrorState, PageHeader, Pill, Skeleton, cx, inputCls } from '../components/ui'
import { fmtDateTime } from '../lib/format'

// Action kinds the mock (and the audit trail in general) records.
const ACTIONS = {
  review: { label: 'Review', tone: 'violet' },
  recheck: { label: 'Rescan', tone: 'green' },
  scan: { label: 'Scan', tone: 'red' },
  site: { label: 'Website', tone: 'blue' },
  role: { label: 'Role', tone: 'amber' },
  settings: { label: 'Settings', tone: 'slate' },
}

export default function AuditLog() {
  const [q, setQ] = useState('')
  const [kind, setKind] = useState('')
  const a = useQuery({ queryKey: ['audit'], queryFn: api.audit })

  const rows = useMemo(() => {
    const term = q.toLowerCase()
    return (a.data ?? []).filter(
      (e) => (!kind || e.action === kind) && (!term || [e.actor, e.detail, e.object].some((t) => (t ?? '').toLowerCase().includes(term)))
    )
  }, [a.data, q, kind])

  const counts = useMemo(() => (a.data ?? []).reduce((m, e) => ((m[e.action] = (m[e.action] ?? 0) + 1), m), {}), [a.data])

  return (
    <>
      <PageHeader title="Audit log" subtitle="Every reviewer decision, scan outcome and configuration change, newest first. Audit records are kept for the retention period set in Administration." />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <div className="relative min-w-56 flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input className={cx(inputCls, 'pl-9')} placeholder="Search people, actions or targets" aria-label="Search the audit log" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by action">
            <button aria-pressed={kind === ''} onClick={() => setKind('')} className={cx('rounded-full border px-3 py-1.5 text-xs font-medium transition-colors', kind === '' ? 'border-ink bg-ink text-on-ink' : 'border-line bg-surface hover:bg-hover')}>All actions</button>
            {Object.entries(ACTIONS).filter(([k]) => counts[k]).map(([k, v]) => (
              <button key={k} aria-pressed={kind === k} onClick={() => setKind(kind === k ? '' : k)} className={cx('rounded-full border px-3 py-1.5 text-xs font-medium transition-colors', kind === k ? 'border-ink bg-ink text-on-ink' : 'border-line bg-surface hover:bg-hover')}>{v.label} <span className="opacity-60">{counts[k]}</span></button>
            ))}
          </div>
        </div>

        {a.isLoading ? <div className="space-y-2 p-4">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-14" />)}</div>
          : a.error ? <ErrorState error={a.error} onRetry={a.refetch} />
          : !rows.length ? <Empty title="No matching activity" hint="Try a different search or action filter." />
          : (
            <ul className="divide-y divide-line">
              {rows.map((e) => (
                <li key={e.id} className="flex items-start gap-3 px-5 py-3.5">
                  <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-canvas text-muted"><ScrollText size={15} aria-hidden="true" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm">
                      <span className="font-medium">{e.actor}</span>{' '}
                      <span className="text-muted">·</span>{' '}
                      {e.incident_id ? <Link to={`/incidents/${e.incident_id}`} className="font-medium text-brand hover:underline">{e.detail}</Link> : e.detail}
                    </p>
                    <p className="mt-0.5 text-xs text-muted">{fmtDateTime(e.at)}{e.object && !e.incident_id ? ` · ${e.object}` : ''}</p>
                  </div>
                  <Pill tone={ACTIONS[e.action]?.tone}>{ACTIONS[e.action]?.label ?? e.action}</Pill>
                </li>
              ))}
            </ul>
          )}
        {rows.length > 0 && <p className="border-t border-line px-5 py-3 text-xs text-muted">{rows.length} record{rows.length === 1 ? '' : 's'}</p>}
      </Card>
    </>
  )
}
