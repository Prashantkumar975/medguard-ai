import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Bell, CheckCheck, CircleCheck, ScanLine, ShieldAlert } from 'lucide-react'
import { api } from '../api/endpoints'
import { Button, Card, Empty, ErrorState, PageHeader, Segmented, Skeleton, cx, useToast } from '../components/ui'
import { timeAgo } from '../lib/format'

// Icon + colour per notification kind. Findings colour by priority.
const KIND = {
  finding: { icon: ShieldAlert, tone: 'bg-blush text-blush-ink' },
  scan_failed: { icon: ScanLine, tone: 'bg-butter text-butter-ink' },
  resolved: { icon: CircleCheck, tone: 'bg-sage text-sage-ink' },
}

export default function Notifications() {
  const qc = useQueryClient()
  const toast = useToast()
  const [filter, setFilter] = useState('all')
  const n = useQuery({ queryKey: ['notifications'], queryFn: api.notifications })

  const readAll = useMutation({
    mutationFn: api.markAllNotificationsRead,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['notifications'] }); toast('All notifications marked as read') },
  })

  // Opening a notification marks just that one as read.
  const readOne = useMutation({
    mutationFn: (id) => api.markNotificationRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })

  const rows = (n.data ?? []).filter((x) => filter === 'all' || !x.read)
  const unread = (n.data ?? []).filter((x) => !x.read).length

  return (
    <>
      <PageHeader
        title="Notifications"
        subtitle={unread ? `${unread} unread update${unread === 1 ? '' : 's'} from scans and reviews.` : 'You are up to date.'}
      >
        <Segmented
          label="Filter notifications" value={filter} onChange={setFilter}
          options={[{ value: 'all', label: 'All', text: 'All' }, { value: 'unread', label: 'Unread', text: `Unread${unread ? ` (${unread})` : ''}` }]}
        />
        <Button variant="outline" disabled={!unread || readAll.isPending} onClick={() => readAll.mutate()}><CheckCheck size={16} />Mark all read</Button>
      </PageHeader>

      <Card>
        {n.isLoading ? <div className="space-y-2 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
          : n.error ? <ErrorState error={n.error} onRetry={n.refetch} />
          : !rows.length ? (
            <Empty
              title={filter === 'unread' ? 'No unread notifications' : 'No notifications yet'}
              hint={filter === 'unread' ? 'New findings and scan results will appear here.' : 'MedGuard notifies you when a scan fails, a critical finding is raised, or a finding is resolved.'}
            >
              {filter === 'unread' && <Button variant="outline" size="sm" onClick={() => setFilter('all')}>Show all</Button>}
            </Empty>
          ) : (
            <ul className="divide-y divide-line">
              {rows.map((x) => {
                const { icon: Icon, tone } = KIND[x.kind] ?? KIND.finding
                return (
                  <li key={x.id} className={cx('transition-colors hover:bg-hover', !x.read && 'bg-brand-soft/30')}>
                    <Link to={x.href} onClick={() => !x.read && readOne.mutate(x.id)} className="flex items-start gap-3 px-5 py-4">
                      <span className={cx('mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl', tone)}><Icon size={17} aria-hidden="true" /></span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className={cx('truncate text-sm', x.read ? 'font-medium text-muted' : 'font-semibold')}>{x.title}</p>
                          {!x.read && <span className="h-2 w-2 shrink-0 rounded-full bg-brand" aria-label="Unread" />}
                        </div>
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted">{x.detail}</p>
                      </div>
                      <span className="shrink-0 whitespace-nowrap text-xs text-muted">{timeAgo(x.at)}</span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
      </Card>

      <p className="mt-4 flex items-center gap-2 text-xs text-muted">
        <Bell size={13} aria-hidden="true" />
        Finding notifications shown here follow the priority threshold in Administration.
      </p>
    </>
  )
}
