import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { api } from '../api/endpoints'
import { Card, Empty, ErrorState, PageHeader, PriorityBadge, Select, Skeleton, StatusBadge, VerdictBadge, cx, inputCls, toneDot } from '../components/ui'
import { PRIORITIES, STATUSES, VERDICTS } from '../lib/constants'
import { fmtDate, timeAgo } from '../lib/format'

export default function Queue() {
  const [sp, setSp] = useSearchParams()
  const nav = useNavigate()
  const f = { q: sp.get('q') ?? '', priority: sp.get('priority') ?? '', verdict: sp.get('verdict') ?? '', status: sp.get('status') ?? 'active' }
  const set = (k, v) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); setSp(n, { replace: true }) }
  const q = useQuery({ queryKey: ['incidents', f], queryFn: () => api.incidents(f), placeholderData: (p) => p })
  const reset = () => setSp({}, { replace: true })
  const filtered = f.q || f.priority || f.verdict || f.status !== 'active'

  // Active filters, each individually removable, shown above the results.
  const chips = [
    f.q && { label: `Search: \u201c${f.q}\u201d`, clear: () => set('q', '') },
    f.priority && { label: `${PRIORITIES[f.priority].label} priority`, clear: () => set('priority', '') },
    f.verdict && { label: VERDICTS[f.verdict].label, clear: () => set('verdict', '') },
    f.status !== 'active' && { label: `Status: ${f.status === 'all' ? 'All statuses' : STATUSES[f.status]?.label ?? f.status}`, clear: () => set('status', '') },
  ].filter(Boolean)

  return (
    <>
      <PageHeader title="Investigation queue" subtitle="Findings that need a clinical reviewer, with the most urgent first." />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <div className="relative min-w-56 flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input className={cx(inputCls, 'pl-9')} placeholder="Search claims, drugs or sites" aria-label="Search findings" value={f.q} onChange={(e) => set('q', e.target.value)} />
          </div>
          <div className="flex gap-1.5" role="group" aria-label="Filter by priority">
            {Object.entries(PRIORITIES).map(([k, v]) => (
              <button key={k} aria-pressed={f.priority === k} onClick={() => set('priority', f.priority === k ? '' : k)} className={cx('rounded-full border px-3 py-1.5 text-xs font-medium transition-colors', f.priority === k ? 'border-ink bg-ink text-on-ink' : 'border-line bg-surface hover:bg-hover')}>{v.label}</button>
            ))}
          </div>
          <Select
            ariaLabel="Filter by verdict" className="min-w-52" block={false} value={f.verdict} onChange={(v) => set('verdict', v)}
            options={[{ value: '', label: 'All verdicts' }, ...Object.entries(VERDICTS).filter(([k]) => k !== 'SUPPORTED').map(([k, v]) => ({ value: k, label: v.label, dot: toneDot(v.tone) }))]}
          />
          <Select
            ariaLabel="Filter by status" className="min-w-44" block={false} value={f.status} onChange={(v) => set('status', v)}
            options={[{ value: 'active', label: 'Needs action' }, { value: 'all', label: 'All statuses' }, ...Object.entries(STATUSES).map(([k, v]) => ({ value: k, label: v.label, dot: toneDot(v.tone) }))]}
          />
        </div>

        {chips.length > 0 && q.data?.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-b border-line bg-canvas/60 px-4 py-2.5">
            <span className="text-xs text-muted">Filters</span>
            {chips.map((c) => (
              <button
                key={c.label} type="button" onClick={c.clear} aria-label={`Remove filter: ${c.label}`}
                className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface py-1 pl-2.5 pr-1.5 text-xs font-medium transition-colors hover:bg-hover"
              >
                {c.label}
                <span className="grid h-4 w-4 place-items-center rounded-full text-muted transition-colors hover:bg-ink/10 hover:text-ink"><X size={11} /></span>
              </button>
            ))}
            <button type="button" onClick={reset} className="ml-auto text-xs font-medium text-brand hover:underline">Clear all</button>
          </div>
        )}

        {q.isLoading ? <div className="space-y-2 p-4">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-14" />)}</div>
          : q.error ? <ErrorState error={q.error} onRetry={q.refetch} />
          : !q.data.length ? (
            <Empty title={filtered ? 'No findings match these filters' : 'The queue is clear'} hint={filtered ? 'Try removing a filter.' : 'New findings appear here after the next scan.'}>
              {filtered && <button onClick={reset} className="text-sm font-medium text-brand underline">Clear filters</button>}
            </Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-line text-xs text-muted"><tr>{['Priority', 'Finding', 'Verdict', 'Evidence', 'Status', 'Raised'].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
                <tbody className="divide-y divide-line">
                  {q.data.map((i) => (
                    <tr key={i.id} tabIndex={0} onClick={() => nav(`/incidents/${i.id}`)} onKeyDown={(e) => e.key === 'Enter' && nav(`/incidents/${i.id}`)} className="cursor-pointer transition-colors hover:bg-hover">
                      <td className="px-4 py-3.5"><PriorityBadge value={i.priority} /></td>
                      <td className="max-w-md px-4 py-3.5">
                        <Link to={`/incidents/${i.id}`} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>{i.title}</Link>
                        <p className="mt-0.5 truncate text-xs text-muted">“{i.claim_statement}”</p>
                        <p className="mt-0.5 text-xs text-muted"><span className="font-mono">{i.id}</span> on {i.site}</p>
                      </td>
                      <td className="px-4 py-3.5"><VerdictBadge value={i.verdict} /></td>
                      <td className="px-4 py-3.5 text-xs text-muted"><p className="text-sm text-ink">{i.evidence_authority}</p>{fmtDate(i.evidence_date)}</td>
                      <td className="px-4 py-3.5"><StatusBadge value={i.status} /></td>
                      <td className="whitespace-nowrap px-4 py-3.5 text-muted">{timeAgo(i.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        {q.data?.length > 0 && <p className="border-t border-line px-4 py-3 text-xs text-muted">{q.data.length} finding{q.data.length > 1 ? 's' : ''}</p>}
      </Card>
    </>
  )
}
