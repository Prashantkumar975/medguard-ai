import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Loader2 } from 'lucide-react'
import { api } from '../api/endpoints'
import { Banner } from './ui'

/**
 * Live progress banner for a scan started from the UI.
 * Polls every second while the scan runs, then invalidates the lists it affects.
 */
export default function ScanBanner({ id, domain, onClose }) {
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
