import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowUpRight, BadgeCheck, ChevronRight, CircleAlert, Info, OctagonAlert, ScanSearch, ShieldAlert, Timer, TriangleAlert } from 'lucide-react'
import { api } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { Card, CardHead, Empty, ErrorState, PageHeader, Pill, PriorityBadge, Skeleton, Spark, cx, Button } from '../components/ui'
import { ActivityChart, VerdictChart } from '../components/charts'
import { PRIORITIES } from '../lib/constants'
import { timeAgo } from '../lib/format'

// Pastel tile + matching icon colour. Both flip automatically in dark mode.
const TILES = [
  ['critical', 'bg-blush', 'text-blush-ink', OctagonAlert],
  ['high', 'bg-butter', 'text-butter-ink', TriangleAlert],
  ['medium', 'bg-sky', 'text-sky-ink', CircleAlert],
  ['low', 'bg-sage', 'text-sage-ink', Info],
]
const KPI_STYLE = {
  open: ['bg-blush', 'text-blush-ink', ShieldAlert],
  pages: ['bg-sky', 'text-sky-ink', ScanSearch],
  claims: ['bg-mint', 'text-mint-ink', BadgeCheck],
  review: ['bg-lilac', 'text-lilac-ink', Timer],
}

export default function Dashboard() {
  const { user } = useAuth()
  const a = useQuery({ queryKey: ['analytics'], queryFn: api.analytics })
  const inc = useQuery({ queryKey: ['incidents', { status: 'active' }], queryFn: () => api.incidents({ status: 'active' }) })
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const first = user.name.replace('Dr. ', '').split(' ')[0]
  const open = a.data?.kpis.find((k) => k.key === 'open')?.value

  if (a.error) return <ErrorState error={a.error} onRetry={a.refetch} />

  return (
    <>
      <PageHeader title={`${greeting}, ${first}`} subtitle={a.data ? `${open} findings are waiting for clinical review.` : 'Loading today\u2019s activity'}>
        <Link to="/sites"><Button variant="outline">Manage websites</Button></Link>
        <Link to="/queue"><Button variant="brand">Open the queue</Button></Link>
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {(a.data?.kpis ?? [null, null, null, null]).map((k, i) => (
          <Card key={k?.key ?? i} className="p-5">
            {k ? (() => {
              const [bg, ink, Icon] = KPI_STYLE[k.key] ?? KPI_STYLE.open
              return (
                <>
                  <div className="flex items-center gap-3">
                    <span className={cx('grid h-9 w-9 shrink-0 place-items-center rounded-xl', bg, ink)}><Icon size={18} aria-hidden="true" /></span>
                    <p className="text-sm text-muted">{k.label}</p>
                  </div>
                  <div className="mt-4 flex items-end justify-between gap-2">
                    <div>
                      <p className="font-display text-[34px] font-bold leading-none">{typeof k.value === 'number' ? k.value.toLocaleString() : k.value}</p>
                      <p className="mt-2 text-xs text-muted">{k.delta}</p>
                    </div>
                    <Spark data={k.series} className={ink} />
                  </div>
                </>
              )
            })() : <><Skeleton className="h-4 w-28" /><Skeleton className="mt-4 h-9 w-20" /></>}
          </Card>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {TILES.map(([p, bg, ink, Icon]) => (
          <Link key={p} to={`/queue?priority=${p}`} className={cx('group rounded-2xl p-5 transition-transform hover:-translate-y-0.5', bg)}>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2.5 text-sm font-medium">
                <span className={cx('grid h-8 w-8 place-items-center rounded-lg bg-surface/60', ink)}><Icon size={16} aria-hidden="true" /></span>
                {PRIORITIES[p].label} priority
              </span>
              <ArrowUpRight size={16} className="opacity-50 transition-opacity group-hover:opacity-100" />
            </div>
            <p className="mt-5 font-display text-4xl font-bold leading-none">{a.data ? a.data.by_priority[p] : '–'}</p>
            <p className="mt-1 text-xs text-ink/70">open findings</p>
          </Link>
        ))}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.7fr_1fr]">
        <ActivityChart data={a.data?.scan_activity} />
        <VerdictChart data={a.data?.by_verdict} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <Card>
          <CardHead title="Needs your review" hint="Highest priority first" action={<Link to="/queue" className="text-sm font-medium text-brand">View all</Link>} />
          {inc.isLoading ? <div className="space-y-2 p-5"><Skeleton className="h-12" /><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
            : inc.error ? <ErrorState error={inc.error} onRetry={inc.refetch} />
            : !inc.data.length ? <Empty title="Nothing to review" hint="New findings appear here after the next scan." />
            : (
              <ul className="divide-y divide-line">
                {inc.data.slice(0, 5).map((i) => (
                  <li key={i.id}>
                    <Link to={`/incidents/${i.id}`} className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-hover">
                      <PriorityBadge value={i.priority} />
                      <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{i.title}</p><p className="truncate text-xs text-muted">{i.site} · raised {timeAgo(i.created_at)}</p></div>
                      <ChevronRight size={16} className="text-muted" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
        </Card>

        <Card>
          <CardHead title="Recent scans" hint="Latest agent runs" />
          <ul className="divide-y divide-line">
            {a.data?.recent_runs.map((r) => (
              <li key={r.id} className="flex items-center gap-3 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{r.site}</p>
                  <p className="truncate text-xs text-muted">{r.status === 'failed' ? r.error : `${r.pages} pages, ${r.changed} changed, ${r.duration_s}s`}</p>
                </div>
                <div className="text-right"><Pill tone={r.status === 'failed' ? 'red' : 'green'}>{r.status === 'failed' ? 'Failed' : 'Completed'}</Pill><p className="mt-1 text-xs text-muted">{timeAgo(r.at)}</p></div>
              </li>
            )) ?? <li className="p-5"><Skeleton className="h-32" /></li>}
          </ul>
        </Card>
      </div>
    </>
  )
}
