import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { api } from '../api/endpoints'
import { Button, Card, CardHead, Empty, ErrorState, PageHeader, Segmented, Skeleton, cx, useToast } from '../components/ui'
import { PRIORITIES, STATUSES, VERDICTS } from '../lib/constants'
import { fmtDate } from '../lib/format'

const DAYS = 864e5
// Same dot colours the Pill component uses, as bar fills.
const BAR = { green: 'bg-emerald-400', red: 'bg-rose-400', amber: 'bg-amber-300', blue: 'bg-sky-400', slate: 'bg-stone-400', orange: 'bg-orange-300' }

function Breakdown({ title, hint, rows, total }) {
  return (
    <Card>
      <CardHead title={title} hint={hint} />
      <ul className="space-y-3 px-5 pb-5">
        {rows.map(([label, count, tone]) => (
          <li key={label}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span>{label}</span>
              <span className="font-medium">{count}<span className="ml-1.5 text-xs font-normal text-muted">{total ? `${Math.round((count / total) * 100)}%` : ''}</span></span>
            </div>
            <div className="mt-1.5 h-1.5 rounded-full bg-track">
              <div className={cx('h-1.5 rounded-full', BAR[tone] ?? 'bg-stone-400')} style={{ width: `${total ? Math.max(2, (count / total) * 100) : 0}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function Reports() {
  const toast = useToast()
  const [days, setDays] = useState(30)
  const all = useQuery({ queryKey: ['incidents', { status: 'all' }], queryFn: () => api.incidents({ status: 'all' }) })

  const rows = useMemo(() => {
    if (!all.data) return []
    const cutoff = Date.now() - days * DAYS
    return all.data.filter((i) => new Date(i.created_at).getTime() >= cutoff)
  }, [all.data, days])

  const by = (key, defs) => defs.map(([k, label, tone]) => [label, rows.filter((r) => r[key] === k).length, tone])
  const total = rows.length
  const closed = rows.filter((r) => ['resolved', 'dismissed'].includes(r.status)).length

  const perSite = useMemo(() => {
    const map = new Map()
    for (const r of rows) {
      const e = map.get(r.site) ?? { site: r.site, total: 0, critical: 0, closed: 0 }
      e.total++
      if (r.priority === 'critical') e.critical++
      if (['resolved', 'dismissed'].includes(r.status)) e.closed++
      map.set(r.site, e)
    }
    return [...map.values()].sort((a, b) => b.total - a.total)
  }, [rows])

  const exportCsv = () => {
    const cols = ['id', 'title', 'site', 'priority', 'verdict', 'status', 'claim_statement', 'evidence_authority', 'evidence_date', 'created_at']
    const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
    const csv = [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `medguard-findings-${days}d.csv`
    a.click()
    URL.revokeObjectURL(url)
    toast(`Exported ${rows.length} findings to CSV`)
  }

  return (
    <>
      <PageHeader title="Reports" subtitle={`Findings raised in the last ${days} days, across every monitored website.`}>
        <Button variant="outline" onClick={exportCsv} disabled={!total}><Download size={16} />Export CSV</Button>
      </PageHeader>

      <div className="mb-4 flex items-center gap-3">
        <span className="text-sm text-muted">Period</span>
        <Segmented
          label="Report period" value={days} onChange={setDays}
          options={[{ value: 7, label: '7 days', text: '7 days' }, { value: 30, label: '30 days', text: '30 days' }, { value: 90, label: '90 days', text: '90 days' }]}
        />
      </div>

      {all.isLoading ? (
        <div className="space-y-4"><Skeleton className="h-24" /><div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-64" /><Skeleton className="h-64" /><Skeleton className="h-64" /></div></div>
      ) : all.error ? <ErrorState error={all.error} onRetry={all.refetch} /> : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="p-5"><p className="text-sm text-muted">Findings raised</p><p className="mt-2 font-display text-[34px] font-bold leading-none">{total}</p><p className="mt-2 text-xs text-muted">across {perSite.length} website{perSite.length === 1 ? '' : 's'}</p></Card>
            <Card className="p-5"><p className="text-sm text-muted">Critical or high</p><p className="mt-2 font-display text-[34px] font-bold leading-none">{rows.filter((r) => ['critical', 'high'].includes(r.priority)).length}</p><p className="mt-2 text-xs text-muted">priority given by harm and exposure</p></Card>
            <Card className="p-5"><p className="text-sm text-muted">Closed by a reviewer</p><p className="mt-2 font-display text-[34px] font-bold leading-none">{closed}</p><p className="mt-2 text-xs text-muted">{total ? `${Math.round((closed / total) * 100)}%` : '0%'} resolved or dismissed</p></Card>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <Breakdown title="By verdict" hint="How claims compared with the evidence" total={total} rows={by('verdict', Object.entries(VERDICTS).map(([k, v]) => [k, v.label, v.tone]))} />
            <Breakdown title="By priority" hint="Risk rating at the time of the finding" total={total} rows={by('priority', Object.entries(PRIORITIES).map(([k, v]) => [k, v.label, v.tone]))} />
            <Breakdown title="By status" hint="Where each finding sits in the workflow" total={total} rows={by('status', Object.entries(STATUSES).map(([k, v]) => [k, v.label, v.tone]))} />
          </div>

          <Card className="mt-4 overflow-hidden">
            <CardHead title="By website" hint="Sites with at least one finding in this period" />
            {!perSite.length ? <Empty title="No findings in this period" hint="Widen the period, or wait for the next scan to complete." /> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-line text-xs text-muted"><tr>{['Website', 'Findings', 'Critical', 'Closed'].map((h) => <th key={h} className="px-5 py-3 font-medium">{h}</th>)}</tr></thead>
                  <tbody className="divide-y divide-line">
                    {perSite.map((s) => (
                      <tr key={s.site} className="transition-colors hover:bg-hover">
                        <td className="px-5 py-3.5 font-medium">{s.site}</td>
                        <td className="px-5 py-3.5">{s.total}</td>
                        <td className="px-5 py-3.5">{s.critical}</td>
                        <td className="px-5 py-3.5">{s.closed}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="border-t border-line px-5 py-3 text-xs text-muted">Report generated {fmtDate(new Date().toISOString())}. Exports contain the same rows shown here, including claim text and evidence references.</p>
          </Card>
        </>
      )}
    </>
  )
}
