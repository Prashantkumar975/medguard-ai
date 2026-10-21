import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { api } from '../api/endpoints'
import { Card, Empty, ErrorState, PageHeader, Skeleton, cx, inputCls } from '../components/ui'
import { fmtDateTime } from '../lib/format'

export default function Claims() {
  // TEMP: ?boom=1 renders the custom error page for preview — remove when done
  if (new URLSearchParams(window.location.search).has('boom')) throw new Error('Test crash: previewing the custom error page')
  const [q, setQ] = useState('')
  const [dq, setDq] = useState('')
  useEffect(() => { const t = setTimeout(() => setDq(q), 250); return () => clearTimeout(t) }, [q])
  const c = useQuery({ queryKey: ['claims', dq], queryFn: () => api.claims({ q: dq }), placeholderData: keepPreviousData })

  return (
    <>
      <PageHeader title="Claims" subtitle="Medical statements MedGuard extracted from monitored pages." />
      <Card>
        <div className="border-b border-line p-4">
          <div className="relative max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input className={cx(inputCls, 'pl-9')} placeholder="Search claim text" aria-label="Search claims" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>
        {c.isLoading ? <div className="space-y-2 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
          : c.error ? <ErrorState error={c.error} onRetry={c.refetch} />
          : !c.data.length ? <Empty title="No claims found" hint="Try different words from the statement." />
          : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-line text-xs text-muted"><tr>{['Claim', 'Page', 'Captured', 'Finding'].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
                <tbody className="divide-y divide-line">
                  {c.data.map((x) => (
                    <tr key={x.id} className="transition-colors hover:bg-hover">
                      <td className="max-w-md px-4 py-3.5"><p>“{x.statement}”</p><p className="mt-0.5 text-xs text-muted">{x.context}</p></td>
                      <td className="px-4 py-3.5 text-xs"><a href={x.page_url} target="_blank" rel="noreferrer" className="text-brand hover:underline">{x.page_url.replace('https://', '')}</a></td>
                      <td className="whitespace-nowrap px-4 py-3.5 text-muted">{fmtDateTime(x.snapshot_fetched_at)}</td>
                      <td className="px-4 py-3.5">{x.incident_id ? <Link to={`/incidents/${x.incident_id}`} className="font-mono text-xs text-brand hover:underline">{x.incident_id}</Link> : <span className="text-muted">None</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>
    </>
  )
}
