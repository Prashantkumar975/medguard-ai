import { Link } from 'react-router-dom'
import { ChevronRight, FileText, Globe, ListChecks, ScanSearch, ShieldCheck, Users } from 'lucide-react'
import { USE_MOCK } from '../api/client'
import { Card, CardHead, PageHeader, Pill, cx } from '../components/ui'
import { PRIORITIES, STATUSES, VERDICTS } from '../lib/constants'

/* The seven detection stages shown in every incident's trace. */
const PIPELINE = [
  ['Discovery', 'The crawler checks each monitored page on its schedule and stores a snapshot when the content changes. It respects robots.txt and rate limits.'],
  ['Extraction', 'Medical claims are extracted from the page text together with their surrounding context.'],
  ['Guideline Intelligence', 'Each claim is matched to an authoritative reference — an FDA Drug Safety Communication or an openFDA drug label.'],
  ['Verification', 'Hybrid retrieval and context filters confirm the right passage of the reference applies to the claim.'],
  ['Contradiction', 'Rule checks and natural-language inference compare the claim with the evidence and choose a verdict.'],
  ['Risk Assessment', 'A priority is computed from potential harm, patient exposure, evidence strength and uncertainty.'],
  ['Alert', 'An incident is created and reviewers are notified. Nothing is published or corrected automatically.'],
]

const ROLES_TABLE = [
  ['Administrator', 'Manage websites, users and settings; reviews findings too.'],
  ['Clinical reviewer', 'Review findings, run scans and record decisions.'],
  ['Viewer', 'Read-only access to dashboards, queues and reports.'],
]

/* FAQ answers are checked against the actual behaviour of this app. */
const FAQ = [
  ['What do the verdicts mean?',
    <>
      Every claim found on a monitored page is compared with the matched evidence and given one of five verdicts:{' '}
      <strong>Supported</strong> (matches the current evidence), <strong>Potential contradiction</strong> (conflicts with it), <strong>Possibly outdated</strong> (was correct before a recent revision), <strong>Incomplete information</strong> (missing important context, such as a subgroup dose limit), or <strong>Insufficient evidence</strong> (neither supports nor refutes it — it is sent to a human instead of guessing).
    </>],
  ['What do the priorities mean?',
    <>
      Critical, High, Medium and Low reflect the risk rating the assessment stage computed: the potential harm of following the claim, how many patients it could reach, the strength of the evidence, and the remaining uncertainty. Critical findings appear first in the queue and in the sidebar badge.
    </>],
  ['What happens after a reviewer confirms an issue?',
    <>
      The incident moves to <strong>Awaiting correction</strong> so the site owner can fix the page. Once the page is rescanned and the conflict is gone, a recheck marks it <strong>Resolved</strong>. Reviewers can also dismiss a finding as a false alarm, or keep it <strong>In review</strong> while gathering more information. Every decision needs a written rationale of at least 10 characters and is recorded in the <Link to="/audit" className="text-brand underline">audit log</Link>.
    </>],
  ['Does MedGuard give medical advice or correct pages itself?',
    <>No. MedGuard flags potential discrepancies for human review and never edits a monitored site. A qualified clinician approves every correction, and the disclaimer appears in the footer of every page.</>],
  ['Where does the evidence come from?',
    <>Official FDA sources only: <a href="https://www.fda.gov/drugs/drug-safety-and-availability/drug-safety-communications" target="_blank" rel="noreferrer" className="text-brand underline">Drug Safety Communications</a> and <a href="https://open.fda.gov/apis/drug/label/" target="_blank" rel="noreferrer" className="text-brand underline">openFDA drug labels</a>. The Medical library lists every reference document with its version and effective date.</>],
  ['Which websites can be monitored?',
    <>Only approved public healthcare sites, currently in the United States jurisdiction. The crawler follows robots.txt and applies rate limits, and an administrator can pause monitoring for any site at any time.</>],
  [USE_MOCK ? 'What does the “Mock data” badge mean?' : 'How do I connect the live API?',
    USE_MOCK
      ? <>This deployment is running on a built-in sample dataset — every drug, website and document is fictional. Set <code className="rounded bg-canvas px-1 py-0.5 font-mono text-xs">VITE_USE_MOCK=false</code> in <code className="rounded bg-canvas px-1 py-0.5 font-mono text-xs">.env</code> and point <code className="rounded bg-canvas px-1 py-0.5 font-mono text-xs">VITE_API_URL</code> at the FastAPI server to use real data.</>
      : <>This deployment is connected to the API at the URL in <code className="rounded bg-canvas px-1 py-0.5 font-mono text-xs">VITE_API_URL</code>. If you see sample data instead, set <code className="rounded bg-canvas px-1 py-0.5 font-mono text-xs">VITE_USE_MOCK=true</code>.</>],
  ['Who can see what?',
    <>Administrators manage websites, users and settings; clinical reviewers triage the queue and record decisions; viewers have read-only access. Use “Preview as role” in the sidebar (mock mode) to check what each role sees.</>],
]

export default function Help() {
  return (
    <>
      <PageHeader title="Help & about" subtitle="What MedGuard AI does, how findings are produced, and answers to common questions." />

      {/* About */}
      <Card>
        <CardHead title="About MedGuard AI" hint="Clinical misinformation monitoring" />
        <div className="space-y-3 px-5 pb-5 text-sm leading-relaxed">
          <p>
            MedGuard AI continuously monitors approved healthcare websites for medical claims that conflict with current FDA
            guidance. It extracts claims from changed pages, matches them against official references, and raises a finding
            whenever the two disagree — so clinical reviewers can act on potential misinformation within hours, not weeks.
          </p>
          <p>
            <strong>MedGuard flags discrepancies for human review. It does not provide medical advice</strong> — a qualified
            clinician approves every correction, and nothing is changed on a monitored site automatically.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Pill tone="green">Human-in-the-loop</Pill>
            <Pill tone="blue">FDA sources only</Pill>
            <Pill tone="slate">United States jurisdiction</Pill>
            {USE_MOCK && <Pill tone="amber">Sample data</Pill>}
          </div>
        </div>
      </Card>

      {/* Pipeline */}
      <Card className="mt-4">
        <CardHead title="How a finding is produced" hint="The same seven stages run for every claim, and each one is recorded in the incident trace" />
        <ol className="space-y-3 px-5 pb-5">
          {PIPELINE.map(([name, text], i) => (
            <li key={name} className="flex gap-3">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-soft text-xs font-semibold text-brand">{i + 1}</span>
              <div>
                <p className="text-sm font-medium">{name}</p>
                <p className="mt-0.5 text-sm text-muted">{text}</p>
              </div>
            </li>
          ))}
          <li className="flex gap-3">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand text-xs font-semibold text-on-brand"><Users size={14} aria-hidden="true" /></span>
            <div>
              <p className="text-sm font-medium">Human review</p>
              <p className="mt-0.5 text-sm text-muted">A clinical reviewer confirms, dismisses or requests more information — with a written rationale that is kept in the audit log.</p>
            </div>
          </li>
        </ol>
      </Card>

      {/* Glossary */}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHead title="Verdicts" hint="How a claim compared with the evidence" />
          <ul className="space-y-2.5 px-5 pb-5 text-sm">
            {Object.entries(VERDICTS).map(([k, v]) => (
              <li key={k} className="flex items-center gap-2"><Pill tone={v.tone}>{v.label}</Pill></li>
            ))}
            <li className="pt-1 text-xs text-muted">Only non-Supported verdicts enter the review queue by default.</li>
          </ul>
        </Card>
        <Card>
          <CardHead title="Priorities" hint="Risk rating from harm, exposure, evidence and uncertainty" />
          <ul className="space-y-2.5 px-5 pb-5 text-sm">
            {Object.entries(PRIORITIES).map(([k, v]) => (
              <li key={k} className="flex items-center gap-2"><Pill tone={v.tone}>{v.label}</Pill></li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHead title="Statuses" hint="Where a finding sits in the workflow" />
          <ul className="space-y-2.5 px-5 pb-5 text-sm">
            {Object.entries(STATUSES).map(([k, v]) => (
              <li key={k} className="flex items-center gap-2"><Pill tone={v.tone}>{v.label}</Pill></li>
            ))}
          </ul>
        </Card>
      </div>

      {/* Getting started */}
      <Card className="mt-4">
        <CardHead title="Getting started" hint="Three steps from a blank workspace to your first reviewed finding" />
        <ul className="divide-y divide-line">
          {[
            [Globe, 'Add a website', 'Monitors → Monitored websites → Add website. Only approved public healthcare sites in the US can be added.', '/sites'],
            [ScanSearch, 'Run the first scan', 'Use “Scan now” on the site row. The crawler checks every page and stores snapshots.', '/sites'],
            [ListChecks, 'Review findings', 'New findings appear in the Investigation queue, most urgent first. Open one to see the claim, the evidence and the full trace.', '/queue'],
            [FileText, 'Check what changed', 'The Claims page lists every extracted statement with a link back to its finding, and Reports exports the period to CSV.', '/reports'],
          ].map(([Icon, title, text, to]) => (
            <li key={title}>
              <Link to={to} className="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-hover">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-canvas text-muted"><Icon size={17} aria-hidden="true" /></span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{title}</p>
                  <p className="mt-0.5 text-sm text-muted">{text}</p>
                </div>
                <ChevronRight size={16} className="shrink-0 text-muted" />
              </Link>
            </li>
          ))}
        </ul>
      </Card>

      {/* Roles */}
      <Card className="mt-4">
        <CardHead title="Roles" hint="Permissions are checked on every action" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-xs text-muted"><tr>{['Role', 'Can do'].map((h) => <th key={h} className="px-5 py-3 font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {ROLES_TABLE.map(([role, can]) => (
                <tr key={role}>
                  <td className="whitespace-nowrap px-5 py-3.5 font-medium">{role}</td>
                  <td className="px-5 py-3.5 text-muted">{can}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* FAQ */}
      <Card className="mt-4">
        <CardHead title="Frequently asked questions" />
        <ul className="divide-y divide-line">
          {FAQ.map(([q, a]) => (
            <li key={q} className="px-5 py-4">
              <p className="text-sm font-medium">{q}</p>
              <p className={cx('mt-1 text-sm leading-relaxed text-muted')}>{a}</p>
            </li>
          ))}
        </ul>
      </Card>

      <p className="mt-4 flex items-center gap-2 text-xs text-muted">
        <ShieldCheck size={13} aria-hidden="true" />
        Still stuck? Ask your workspace administrator — audit records are kept for the retention period configured in Administration.
      </p>
    </>
  )
}
