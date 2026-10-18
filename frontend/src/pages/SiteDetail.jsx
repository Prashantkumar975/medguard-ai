import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Clock, FileSearch, Globe, ScanLine } from 'lucide-react'
import { api } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import ScanBanner from '../components/ScanBanner'
import { Banner, Button, Card, CardHead, Empty, ErrorState, PageHeader, Pill, PriorityBadge, Skeleton, StatusBadge, Toggle, VerdictBadge, cx, useToast } from '../components/ui'
import { fmtDateTime, timeAgo } from '../lib/format'

const INTERVALS = [[6, 'Every 6 hours'], [12, 'Every 12 hours'], [24, 'Daily'], [48, 'Every 2 days'], [168, 'Weekly']]
const intervalLabel = (h) => INTERVALS.find(([v]) => v === h)?.[1] ?? `Every ${h}h`
const ACTIVE = ['open', 'in_review', 'awaiting_correction']

function Stat({ icon: Icon, label, value, sub, tone }) {
  return (
    <Card className="p-5">
      <span className={cx('grid h-9 w-9 place-items-center rounded-xl', tone)}><Icon size={18} aria-hidden="true" /></span>
      <p className="mt-4 font-display text-[28px] font-bold leading-none">{value}</p>
      <p className="mt-2 text-sm text-muted">{label}</p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </Card>
  )
}

export default function SiteDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const { can } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [scan, setScan] = useState(null)

  const site = useQuery({ queryKey: ['site', id], queryFn: () => api.site(id) })
  const scans = useQuery({ queryKey: ['scans', id], queryFn: () => api.scans({ site_id: id }) })
  const findings = useQuery({ queryKey: ['incidents', { site: site.data?.domain, status: 'all' }], queryFn: () => api.incidents({ site: site.data?.domain, status: 'all' }), enabled: !!site.data })

  const start = useMutation({ mutationFn: () => api.startScan({ site_id: id }), onSuccess: (sc) => setScan({ id: sc.id, domain: site.data.domain }) })
  const toggle = useMutation({ mutationFn: (enabled) => api.updateSite(id, { enabled }), onSuccess: (_r, enabled) => { qc.invalidateQueries({ queryKey: ['site', id] }); qc.invalidateQueries({ queryKey: ['sites'] }); toast(enabled ? `${site.data.domain} resumed` : `${site.data.domain} paused`) } })

  if (site.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-64" /><div className="grid gap-4 sm:grid-cols-3"><Skeleton className="h-36" /><Skeleton className="h-36" /><Skeleton className="h-36" /></div><Skeleton className="h-64" /></div>
  if (site.error) return <ErrorState error={site.error} onRetry={site.refetch} />

  const s = site.data
  const openFindings = (findings.data ?? []).filter((i) => ACTIVE.includes(i.status))
  const critical = openFindings.filter((i) => i.priority === 'critical').length
  const lastRun = scans.data?.[0]

  return (
    <>
      <button onClick={() => nav('/sites')} className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-ink">
        <ArrowLeft size={15} />All websites
      </button>
      <PageHeader title={s.domain} subtitle={`${s.jurisdiction} · ${s.language.toUpperCase()} · ${s.enabled ? 'monitored' : 'paused'} · last scan ${s.last_scan_at ? timeAgo(s.last_scan_at) : 'never'}`}>
        <label className="flex items-center gap-2 text-sm text-muted">
          Monitoring
          <Toggle label={`Monitor ${s.domain}`} checked={s.enabled} disabled={!can('manageSites') || toggle.isPending} onChange={(v) => toggle.mutate(v)} />
        </label>
        {can('scan') && (
          <Button variant="brand" disabled={!s.enabled || start.isPending || !!scan} onClick={() => start.mutate()}>
            <ScanLine size={16} />Scan now
          </Button>
        )}
      </PageHeader>

      {scan && <ScanBanner {...scan} onClose={() => setScan(null)} />}
      {start.error && <Banner tone="red">{start.error.message}</Banner>}
      {!s.enabled && <Banner tone="slate">Monitoring is paused for this website. Enable it to run scheduled or manual scans.</Banner>}
      {s.last_scan_status === 'failed' && <Banner tone="red">The most recent scan failed. Open the crawl history below for the error, then run a new scan.</Banner>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Globe} tone="bg-sky text-sky-ink" label="Pages under watch" value={s.pages} />
        <Stat icon={Clock} tone="bg-lilac text-lilac-ink" label="Check frequency" value={intervalLabel(s.scan_interval_hours)} />
        <Stat icon={ScanLine} tone={s.last_scan_status === 'failed' ? 'bg-blush text-blush-ink' : 'bg-mint text-mint-ink'} label="Last scan" value={s.last_scan_at ? timeAgo(s.last_scan_at) : 'Never'} sub={s.last_scan_status === 'failed' ? 'Failed' : s.last_scan_status === 'completed' ? `${lastRun?.pages_total ?? s.pages} pages checked` : undefined} />
        <Stat icon={FileSearch} tone={critical ? 'bg-blush text-blush-ink' : 'bg-sage text-sage-ink'} label="Open findings" value={openFindings.length} sub={critical ? `${critical} critical` : 'None critical'} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1.3fr]">
        <Card>
          <CardHead title="Crawl history" hint="Most recent first" />
          {scans.isLoading ? <div className="space-y-2 p-5"><Skeleton className="h-14" /><Skeleton className="h-14" /></div>
            : scans.error ? <ErrorState error={scans.error} onRetry={scans.refetch} />
            : !scans.data.length ? <Empty title="No scans yet" hint="Run the first scan to check the pages on this site." />
            : (
              <ul className="divide-y divide-line">
                {scans.data.map((h) => (
                  <li key={h.id} className="px-5 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">{fmtDateTime(h.started_at)}</p>
                      <Pill tone={h.status === 'failed' ? 'red' : h.status === 'running' ? 'blue' : 'green'}>{h.status === 'failed' ? 'Failed' : h.status === 'running' ? 'Running' : 'Completed'}</Pill>
                    </div>
                    <p className="mt-0.5 text-xs text-muted">
                      {h.status === 'failed' ? h.error : `${h.pages_total} pages, ${h.changed} changed, ${h.claims_extracted} claims`} · {h.trigger} · {h.duration_s}s
                    </p>
                  </li>
                ))}
              </ul>
            )}
        </Card>

        <Card>
          <CardHead title="Findings on this site" hint={`${findings.data?.length ?? 0} total, ${openFindings.length} still open`} action={<Link to={`/queue?status=all&q=${encodeURIComponent(s.domain)}`} className="text-sm font-medium text-brand">Open in queue</Link>} />
          {findings.isLoading ? <div className="space-y-2 p-5"><Skeleton className="h-14" /><Skeleton className="h-14" /></div>
            : findings.error ? <ErrorState error={findings.error} onRetry={findings.refetch} />
            : !findings.data.length ? <Empty title="No findings" hint="Claims on this site have matched the current evidence so far." />
            : (
              <ul className="divide-y divide-line">
                {findings.data.slice(0, 8).map((i) => (
                  <li key={i.id}>
                    <Link to={`/incidents/${i.id}`} className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-hover">
                      <PriorityBadge value={i.priority} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{i.title}</p>
                        <p className="truncate text-xs text-muted">{i.evidence_authority} · raised {timeAgo(i.created_at)}</p>
                      </div>
                      <VerdictBadge value={i.verdict} />
                      <StatusBadge value={i.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
        </Card>
      </div>
    </>
  )
}
