import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Activity, CircleAlert, Clock, Globe, ScanLine, Timer } from 'lucide-react'
import { api } from '../api/endpoints'
import { USE_MOCK } from '../api/client'
import { Card, CardHead, Empty, ErrorState, PageHeader, Pill, Skeleton } from '../components/ui'
import { fmtDateTime, timeAgo } from '../lib/format'

const H = 3600e3

// Next scheduled run, derived the same way the crawler schedules sites.
const nextRun = (s) => {
  if (!s.enabled || !s.last_scan_at) return null
  const t = new Date(s.last_scan_at).getTime() + s.scan_interval_hours * H
  return t
}

// Compact countdown for a future timestamp, e.g. "in 21h".
const until = (t) => {
  const s = (t - Date.now()) / 1000
  if (s <= 0) return 'due now'
  if (s < 3600) return `in ${Math.max(1, Math.round(s / 60))}m`
  return `in ${Math.round(s / 3600)}h`
}

export default function Status() {
  const sites = useQuery({ queryKey: ['sites'], queryFn: api.sites })
  const scans = useQuery({ queryKey: ['scans'], queryFn: () => api.scans({}) })

  const list = sites.data ?? []
  const enabled = list.filter((s) => s.enabled)
  const stale = enabled.filter((s) => s.last_scan_at && Date.now() - new Date(s.last_scan_at).getTime() > s.scan_interval_hours * 2 * H)
  const failedSites = enabled.filter((s) => s.last_scan_status === 'failed')
  const failedRuns = (scans.data ?? []).filter((s) => s.status === 'failed')
  const healthy = !failedSites.length && !stale.length

  const totalPages = enabled.reduce((n, s) => n + s.pages, 0)
  const nextDue = enabled.map(nextRun).filter(Boolean).sort((a, b) => a - b)[0]

  return (
    <>
      <PageHeader title="System status" subtitle="Crawler health across every monitored website, and the schedule for upcoming runs." />

      {sites.isLoading ? <Skeleton className="h-24" /> : (
        <Card className={healthy ? 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-300/20 dark:bg-emerald-400/5' : 'border-amber-200 bg-amber-50/50 dark:border-amber-300/20 dark:bg-amber-300/5'}>
          <div className="flex items-start gap-3 p-5">
            <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${healthy ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-300' : 'bg-amber-100 text-amber-800 dark:bg-amber-300/15 dark:text-amber-200'}`}>
              {healthy ? <Activity size={19} /> : <CircleAlert size={19} />}
            </span>
            <div>
              <p className="font-display text-[15px] font-bold">{healthy ? 'All systems operational' : 'Attention needed'}</p>
              <p className="mt-0.5 text-sm text-muted">
                {healthy
                  ? `${enabled.length} website${enabled.length === 1 ? '' : 's'} monitored, ${totalPages.toLocaleString()} pages under watch.`
                  : [
                      failedSites.length && `${failedSites.length} site${failedSites.length === 1 ? '' : 's'} failed the most recent scan.`,
                      stale.length && `${stale.length} site${stale.length === 1 ? '' : 's'} missed their scheduled check.`,
                    ].filter(Boolean).join(' ')}
              </p>
            </div>
          </div>
        </Card>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          [Globe, 'bg-sky text-sky-ink', `${enabled.length} of ${list.length}`, 'websites monitored', list.length - enabled.length ? `${list.length - enabled.length} paused` : 'none paused'],
          [ScanLine, 'bg-mint text-mint-ink', totalPages.toLocaleString(), 'pages under watch', 'across active sites'],
          [Timer, 'bg-lilac text-lilac-ink', nextDue ? until(nextDue) : '—', nextDue ? 'until the next scheduled run' : 'no run scheduled', nextDue ? `at ${fmtDateTime(nextDue)}` : undefined],
          [Clock, failedRuns.length ? 'bg-blush text-blush-ink' : 'bg-sage text-sage-ink', failedRuns.length, `failed run${failedRuns.length === 1 ? '' : 's'} in history`, 'in the stored crawl history'],
        ].map(([Icon, tone, value, label, sub], i) => (
          <Card key={i} className="p-5">
            <span className={`grid h-9 w-9 place-items-center rounded-xl ${tone}`}><Icon size={18} aria-hidden="true" /></span>
            <p className="mt-4 font-display text-[28px] font-bold leading-none">{value}</p>
            <p className="mt-2 text-sm text-muted">{label}</p>
            {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
          </Card>
        ))}
      </div>

      <Card className="mt-4 overflow-hidden">
        <CardHead title="Website health" hint="Derived from each site's schedule and its most recent scan" />
        {sites.isLoading ? <div className="space-y-2 p-5"><Skeleton className="h-14" /><Skeleton className="h-14" /></div>
          : sites.error ? <ErrorState error={sites.error} onRetry={sites.refetch} />
          : !list.length ? <Empty title="No websites yet" hint="Add a site to start monitoring." > <Link to="/sites" className="text-sm font-medium text-brand underline">Go to Monitored websites</Link></Empty>
          : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-line text-xs text-muted"><tr>{['Website', 'State', 'Last scan', 'Next run', 'Pages'].map((h) => <th key={h} className="px-5 py-3 font-medium">{h}</th>)}</tr></thead>
                <tbody className="divide-y divide-line">
                  {list.map((s) => {
                    const state = !s.enabled ? ['Paused', 'slate'] : s.last_scan_status === 'failed' ? ['Scan failed', 'red'] : stale.includes(s) ? ['Overdue', 'amber'] : ['Healthy', 'green']
                    const due = nextRun(s)
                    return (
                      <tr key={s.id} className="transition-colors hover:bg-hover">
                        <td className="px-5 py-3.5"><Link to={`/sites/${s.id}`} className="font-medium text-brand hover:underline">{s.domain}</Link><p className="text-xs text-muted">{s.scan_interval_hours}h interval</p></td>
                        <td className="px-5 py-3.5"><Pill tone={state[1]}>{state[0]}</Pill></td>
                        <td className="px-5 py-3.5">{s.last_scan_at ? <div><p>{timeAgo(s.last_scan_at)}</p><p className="text-xs text-muted">{fmtDateTime(s.last_scan_at)}</p></div> : <span className="text-muted">Never</span>}</td>
                        <td className="px-5 py-3.5 text-muted">{!s.enabled ? '—' : due ? fmtDateTime(due) : 'After first scan'}</td>
                        <td className="px-5 py-3.5">{s.pages}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
      </Card>

      <Card className="mt-4">
        <CardHead title="Recent failed runs" hint="Crawl errors from the last runs on each site" />
        {scans.isLoading ? <div className="space-y-2 p-5"><Skeleton className="h-14" /></div>
          : !failedRuns.length ? <Empty title="No failed runs" hint="Every stored crawl completed successfully." />
          : (
            <ul className="divide-y divide-line">
              {failedRuns.slice(0, 6).map((r) => (
                <li key={r.id} className="flex items-center gap-3 px-5 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{list.find((s) => s.id === r.site_id)?.domain ?? r.site_id}</p>
                    <p className="truncate text-xs text-muted">{r.error}</p>
                  </div>
                  <div className="text-right">
                    <Pill tone="red">Failed</Pill>
                    <p className="mt-1 text-xs text-muted">{timeAgo(r.started_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        <p className="border-t border-line px-5 py-3 text-xs text-muted">
          {USE_MOCK ? 'Sample environment: health is computed from the built-in mock crawler. ' : ''}Data refreshed when this page opens; scheduled runs continue in the background.
        </p>
      </Card>
    </>
  )
}
