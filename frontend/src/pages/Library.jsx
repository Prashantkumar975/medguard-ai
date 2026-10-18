import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ExternalLink, FileText, Search } from 'lucide-react'
import { api } from '../api/endpoints'
import { Card, CardHead, Empty, ErrorState, PageHeader, Pill, Skeleton, cx, inputCls } from '../components/ui'
import { fmtDate } from '../lib/format'

export default function Library() {
  const [q, setQ] = useState('')
  const [dq, setDq] = useState('')
  const [sel, setSel] = useState(null)
  useEffect(() => { const t = setTimeout(() => setDq(q), 250); return () => clearTimeout(t) }, [q])
  const docs = useQuery({ queryKey: ['references', dq], queryFn: () => api.references({ q: dq }), placeholderData: keepPreviousData })
  const doc = docs.data?.find((d) => d.id === sel) ?? docs.data?.[0]

  return (
    <>
      <PageHeader title="Medical library" subtitle="Official FDA documents that MedGuard checks website claims against." />
      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        <Card className="self-start">
          <div className="border-b border-line p-4">
            <div className="relative"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input className={cx(inputCls, 'pl-9')} placeholder="Search drugs or label text" aria-label="Search the library" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          </div>
          {docs.isLoading ? <div className="space-y-2 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
            : docs.error ? <ErrorState error={docs.error} onRetry={docs.refetch} />
            : !docs.data.length ? <Empty title="No documents found" hint="Try a drug name or a phrase from a label." />
            : (
              <ul className="max-h-[70vh] divide-y divide-line overflow-y-auto">
                {docs.data.map((d) => (
                  <li key={d.id}>
                    <button onClick={() => setSel(d.id)} className={cx('flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-hover', doc?.id === d.id && 'bg-brand-soft/50')}>
                      <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-canvas"><FileText size={15} /></span>
                      <span className="min-w-0"><span className="block truncate text-sm font-medium">{d.title}</span><span className="block text-xs text-muted">{d.doc_type} · {fmtDate(d.effective_date)}</span></span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
        </Card>

        <Card>
          {!doc ? <Empty title="Select a document" hint="Its sections and version details appear here." /> : (
            <>
              <div className="border-b border-line p-5">
                <div className="mb-2 flex flex-wrap gap-2"><Pill tone="green">{doc.authority}</Pill><Pill tone="slate">{doc.doc_type}</Pill></div>
                <h2 className="font-display text-xl font-bold leading-snug">{doc.title}</h2>
                <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
                  <div><dt className="text-xs text-muted">Version</dt><dd>{doc.version}</dd></div>
                  <div><dt className="text-xs text-muted">Effective</dt><dd>{fmtDate(doc.effective_date)}</dd></div>
                  {Object.entries(doc.identifiers).map(([k, v]) => <div key={k}><dt className="text-xs text-muted">{k}</dt><dd>{v}</dd></div>)}
                </dl>
                <a href={doc.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline">Open on FDA.gov<ExternalLink size={13} /></a>
              </div>
              <div className="divide-y divide-line">
                {doc.chunks.map((c, i) => <section key={i} className="p-5"><h3 className="mb-1.5 text-sm font-semibold">{c.section}</h3><p className="max-w-prose text-sm leading-relaxed text-ink/85">{c.text}</p></section>)}
              </div>
            </>
          )}
        </Card>
      </div>
    </>
  )
}
