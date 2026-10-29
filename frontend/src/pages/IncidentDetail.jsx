import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle2, ExternalLink, Globe, RefreshCw, ShieldCheck } from 'lucide-react'
import { api } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { Banner, Button, Card, CardHead, ErrorState, Highlight, PriorityBadge, Skeleton, StatusBadge, VerdictBadge, cx, inputCls, useToast } from '../components/ui'
import { DECISIONS } from '../lib/constants'
import { fmtDate, fmtDateTime } from '../lib/format'

const METERS = [
  ['harm', 'Potential harm', 'bg-rose-400'],
  ['exposure', 'Exposure', 'bg-orange-300'],
  ['evidence_strength', 'Evidence strength', 'bg-brand'],
  ['uncertainty', 'Uncertainty', 'bg-amber-300'],
]

function DecisionPanel({ inc }) {
  const { can } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [decision, setDecision] = useState('confirm')
  const [why, setWhy] = useState('')
  const refresh = () => ['incident', 'incidents', 'analytics'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }))
  const review = useMutation({ mutationFn: () => api.review(inc.id, { decision, rationale: why }), onSuccess: () => { refresh(); toast('Decision saved') } })
  const recheck = useMutation({ mutationFn: () => api.recheck(inc.id), onSuccess: () => { refresh(); toast('Rescan complete. Incident resolved.') } })
  const d = inc.decision

  return (
    <Card>
      <CardHead title="Reviewer decision" hint="Every decision is recorded in the audit trail." />
      <div className="space-y-4 px-5 pb-5">
        {d && (
          <div className="rounded-xl bg-canvas/70 p-3 text-sm">
            <p className="font-medium">{DECISIONS[d.decision]?.label ?? d.decision}</p>
            <p className="mt-1 text-muted">{d.rationale}</p>
            <p className="mt-2 text-xs text-muted">{d.reviewer}, {fmtDateTime(d.at)}</p>
          </div>
        )}

        {inc.status === 'awaiting_correction' && (
          <>
            <p className="text-sm text-muted">MedGuard never edits medical content. Ask the site owner to correct the page, then rescan to check the fix.</p>
            {can('review') && <Button variant="brand" className="w-full" onClick={() => recheck.mutate()} disabled={recheck.isPending}><RefreshCw size={15} className={recheck.isPending ? 'animate-spin' : ''} />{recheck.isPending ? 'Rescanning…' : 'Rescan the page'}</Button>}
            {recheck.error && <Banner tone="red">{recheck.error.message}</Banner>}
          </>
        )}
        {inc.status === 'resolved' && <p className="flex items-center gap-2 text-sm text-emerald-800 dark:text-emerald-300"><CheckCircle2 size={16} />Resolved. The rescan found no conflict.</p>}
        {inc.status === 'dismissed' && <p className="text-sm text-muted">Dismissed as a false alarm. No further action needed.</p>}

        {['open', 'in_review'].includes(inc.status) && (can('review') ? (
          <form onSubmit={(e) => { e.preventDefault(); review.mutate() }} className="space-y-3">
            <fieldset className="space-y-2">
              <legend className="sr-only">Decision</legend>
              {Object.entries(DECISIONS).map(([k, v]) => (
                <label key={k} className={cx('flex cursor-pointer gap-3 rounded-xl border p-3 transition-colors', decision === k ? 'border-brand bg-brand-soft/60' : 'border-line hover:bg-hover')}>
                  <input type="radio" name="decision" className="mt-1 mg-radio" checked={decision === k} onChange={() => setDecision(k)} />
                  <span><span className="block text-sm font-medium">{v.label}</span><span className="block text-xs text-muted">{v.hint}</span></span>
                </label>
              ))}
            </fieldset>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">Rationale</span>
              <textarea rows={3} className={inputCls} placeholder="Explain what you checked and why." value={why} onChange={(e) => setWhy(e.target.value)} aria-required="true" aria-describedby="why-hint" />
              <span id="why-hint" className="mt-1 block text-xs text-muted">{why.trim().length < 10 ? `${10 - why.trim().length} more characters needed` : 'Ready to save'}</span>
            </label>
            {review.error && <p className="text-sm text-red-700 dark:text-red-300" role="alert">{review.error.message}</p>}
            <Button variant="primary" className="w-full" disabled={review.isPending || why.trim().length < 10}>{review.isPending ? 'Saving…' : 'Save decision'}</Button>
          </form>
        ) : <p className="text-sm text-muted">Your role can view this incident but not decide on it.</p>)}
      </div>
    </Card>
  )
}

export default function IncidentDetail() {
  const { id } = useParams()
  const q = useQuery({ queryKey: ['incident', id], queryFn: () => api.incident(id) })
  const [ei, setEi] = useState(0)

  if (q.isLoading) return <div className="space-y-4"><Skeleton className="h-16 w-2/3" /><div className="grid gap-4 md:grid-cols-2"><Skeleton className="h-72" /><Skeleton className="h-72" /></div></div>
  if (q.error) return <Card><ErrorState error={q.error} onRetry={q.refetch} /></Card>
  const inc = q.data
  // Clamp the selected evidence index: `ei` survives navigation between incidents,
  // so a stale value from a multi-source incident would crash a single-source one.
  const ev = inc.evidence[ei] ?? inc.evidence[0]

  return (
    <>
      <Link to="/queue" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"><ArrowLeft size={15} />Back to the queue</Link>
      <div className="mb-6">
        <div className="mb-2 flex flex-wrap items-center gap-2"><span className="font-mono text-xs text-muted">{inc.id}</span><PriorityBadge value={inc.priority} /><VerdictBadge value={inc.verdict} /><StatusBadge value={inc.status} /></div>
        <h1 className="font-display text-[26px] font-bold leading-tight tracking-tight">{inc.title}</h1>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="flex flex-col border-red-200/70 dark:border-red-400/25">
              <CardHead title="On the website" hint={inc.claim.context} />
              <div className="flex-1 px-5 pb-4">
                <a href={inc.page_url} target="_blank" rel="noreferrer" className="mb-3 inline-flex items-center gap-1.5 text-xs text-brand hover:underline"><Globe size={13} />{inc.page_url.replace('https://', '')}</a>
                <blockquote className="font-display text-[19px] leading-snug"><Highlight text={inc.claim.statement} offsets={inc.claim.offsets} kind="claim" /></blockquote>
              </div>
              <div className="border-t border-line px-5 py-3 text-xs text-muted">Captured {fmtDateTime(inc.claim.snapshot_fetched_at)}<br /><span className="font-mono">{inc.claim.content_hash.slice(0, 24)}…</span></div>
            </Card>

            <Card className="flex flex-col border-emerald-200/80 dark:border-emerald-400/25">
              <CardHead title={`Official evidence · ${ev.authority}`} hint={ev.doc_type} />
              {inc.evidence.length > 1 && (
                <div className="flex gap-1.5 px-5 pb-2">{inc.evidence.map((e, i) => <button key={e.id} onClick={() => setEi(i)} className={cx('rounded-full border px-2.5 py-1 text-xs', i === ei ? 'border-ink bg-ink text-on-ink' : 'border-line')}>Source {i + 1}</button>)}</div>
              )}
              <div className="flex-1 px-5 pb-4">
                <p className="text-sm font-medium">{ev.title}</p>
                <p className="mb-3 mt-1 text-xs text-muted">{ev.section} · version {ev.version} · effective {fmtDate(ev.effective_date)}</p>
                <blockquote className="font-display text-[19px] leading-snug"><Highlight text={ev.quote} offsets={ev.offsets} kind="evidence" /></blockquote>
              </div>
              <div className="border-t border-line px-5 py-3"><a href={ev.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-xs font-medium text-brand hover:underline">Open the source document<ExternalLink size={12} /></a></div>
            </Card>
          </div>

          <Card>
            <CardHead title="Why it was flagged" hint="Summary written by the verification agent from the evidence above" />
            <p className="px-5 pb-4 text-sm leading-relaxed">{inc.rationale}</p>
            <div className="grid gap-x-6 gap-y-4 border-t border-line p-5 sm:grid-cols-2">
              {METERS.map(([k, label, color]) => (
                <div key={k}>
                  <div className="mb-1 flex justify-between text-xs"><span className="text-muted">{label}</span><span className="font-medium">{Math.round(inc.risk[k] * 100)}%</span></div>
                  <div className="h-2 rounded-full bg-track"><div className={cx('h-2 rounded-full', color)} style={{ width: `${inc.risk[k] * 100}%` }} /></div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <DecisionPanel inc={inc} />
          <Card>
            <CardHead title="Audit trail" hint={`Agent run ${inc.agent_run_id}`} />
            <ol className="px-5 pb-5">
              {inc.trace.map((t, i) => (
                <li key={i} className="relative flex gap-3 pb-3 last:pb-0">
                  {i < inc.trace.length - 1 && <span className="absolute left-[7px] top-4 h-full w-px bg-line" />}
                  <span className="relative mt-1 grid h-4 w-4 shrink-0 place-items-center rounded-full bg-brand-soft"><ShieldCheck size={10} className="text-brand" /></span>
                  <div><p className="text-sm font-medium">{t.step}</p><p className="text-xs text-muted">{t.detail}</p><p className="text-xs text-muted/80">{fmtDateTime(t.at)}</p></div>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
    </>
  )
}
