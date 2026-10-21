// In-memory fake backend. Every drug, site and document below is FICTIONAL sample data.
// Response shapes here are the contract the real API should match.
const H = 3600e3
const ago = (h) => new Date(Date.now() - h * H).toISOString()
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const clone = (x) => structuredClone(x)
const FDA = 'https://www.fda.gov/drugs/drug-safety-and-availability/drug-safety-communications'
const LABEL = 'https://open.fda.gov/apis/drug/label/'
const hash = (n) => `sha256:${((n * 2654435761) >>> 0).toString(16).padStart(8, '0')}c41e9b07d2`

const docs = {
  zorv: { id: 'ref_zorv', authority: 'FDA', doc_type: 'Drug Safety Communication', title: 'Zorvaxin (zorvaxabide): new contraindication during pregnancy', version: 'v2', effective_date: '2026-08-21', url: FDA, identifiers: { Application: 'NDA 999001' },
    chunks: [{ section: 'Summary', text: 'FDA is notifying healthcare professionals that Zorvaxin tablets are now contraindicated in pregnancy following post-marketing reports of fetal harm.' }, { section: 'Contraindications', text: 'Zorvaxin is contraindicated in pregnant women because of the risk of fetal harm. Women who may become pregnant should use effective contraception during treatment.' }] },
  cardio: { id: 'ref_cardio', authority: 'FDA', doc_type: 'Drug label (openFDA)', title: 'Cardiolamine tablets, prescribing information', version: '2026-05', effective_date: '2026-05-14', url: LABEL, identifiers: { Application: 'NDA 999002', 'Set ID': 'c0a1-7e22' },
    chunks: [{ section: 'Indications and Usage', text: 'Cardiolamine is indicated for the treatment of hypertension in adults.' }, { section: 'Dosage and Administration', text: 'The maximum recommended daily dose is 400 mg in patients with normal renal function. In patients with severe renal impairment (eGFR below 30 mL/min), do not exceed 200 mg per day.' }] },
  gluc: { id: 'ref_gluc', authority: 'FDA', doc_type: 'Drug label (openFDA)', title: 'Glucavane extended-release tablets, prescribing information', version: '2026-07', effective_date: '2026-07-09', url: LABEL, identifiers: { Application: 'NDA 999003' },
    chunks: [{ section: 'Indications and Usage', text: 'Glucavane is indicated as an adjunct to diet and exercise to improve glycemic control in adults with type 2 diabetes.' }, { section: 'Dosage and Administration', text: 'Initiate Glucavane at 500 mg once daily with the evening meal. Increase gradually based on tolerability. The previous twice-daily starting regimen is no longer recommended.' }] },
  nephro: { id: 'ref_nephro', authority: 'FDA', doc_type: 'Drug Safety Communication', title: 'Nephrotil: increased bleeding risk with anticoagulants', version: 'v1', effective_date: '2026-09-02', url: FDA, identifiers: { Application: 'NDA 999004' },
    chunks: [{ section: 'Summary', text: 'FDA has identified a drug interaction between Nephrotil and anticoagulant medicines.' }, { section: 'Drug Interactions', text: 'Concomitant use of Nephrotil with anticoagulants increases the risk of serious bleeding. Monitor patients closely and consider an alternative analgesic.' }] },
  resp: { id: 'ref_resp', authority: 'FDA', doc_type: 'Drug label (openFDA)', title: 'Respirol inhalation aerosol, prescribing information', version: '2026-03', effective_date: '2026-03-30', url: LABEL, identifiers: { Application: 'NDA 999005' },
    chunks: [{ section: 'Indications and Usage', text: 'Respirol is indicated for the relief of bronchospasm in patients with reversible obstructive airway disease.' }, { section: 'Pediatric Use', text: 'Respirol is approved for use in patients 6 years of age and older. Safety and effectiveness in pediatric patients below 6 years have not been established.' }] },
  lumixa: { id: 'ref_lumixa', authority: 'FDA', doc_type: 'Drug label (openFDA)', title: 'Lumixa tablets, prescribing information', version: '2026-02', effective_date: '2026-02-11', url: LABEL, identifiers: { Application: 'NDA 999006' },
    chunks: [{ section: 'Indications and Usage', text: 'Lumixa is indicated for the short-term treatment of insomnia in adults.' }, { section: 'Geriatric Use', text: 'Clinical studies of Lumixa did not include sufficient numbers of subjects aged 65 and over to determine whether they respond differently from younger subjects.' }] },
  derma: { id: 'ref_derma', authority: 'FDA', doc_type: 'Drug label (openFDA)', title: 'Dermacalm topical cream, prescribing information', version: '2026-04', effective_date: '2026-04-22', url: LABEL, identifiers: { Application: 'NDA 999007' },
    chunks: [{ section: 'Indications and Usage', text: 'Dermacalm is indicated for the relief of itching associated with mild eczema.' }, { section: 'Warnings and Precautions', text: 'Do not apply Dermacalm to broken or irritated skin. Avoid contact with eyes and mucous membranes.' }] },
  hep: { id: 'ref_hep', authority: 'FDA', doc_type: 'Drug label (openFDA)', title: 'Hepatrin tablets (human), prescribing information', version: '2026-01', effective_date: '2026-01-19', url: LABEL, identifiers: { Application: 'NDA 999008' },
    chunks: [{ section: 'Indications and Usage', text: 'Hepatrin is indicated to lower cholesterol in adults with hyperlipidemia.' }, { section: 'Contraindications', text: 'Hepatrin tablets are contraindicated in patients with active liver disease.' }] },
}

const seeds = [
  { n: 1048, drug: 'zorv', site: 'testhealth.example', path: '/drugs/zorvaxin/pregnancy', v: 'POTENTIAL_CONTRADICTION', p: 'critical', s: 'open', h: 3, title: 'Zorvaxin: pregnancy safety claim conflicts with new contraindication', ctx: 'Patient FAQ › Special populations', claim: 'Zorvaxin can be taken safely throughout pregnancy and while breastfeeding.', ch: 'taken safely throughout pregnancy', ci: 1, eh: 'contraindicated in pregnant women', why: 'The page says Zorvaxin is safe in pregnancy. The current FDA Drug Safety Communication contraindicates it. Drug, formulation (oral tablet) and population (pregnant adults) all match, so the conflict is direct.', r: [0.95, 0.8, 0.92, 0.08] },
  { n: 1047, drug: 'nephro', site: 'clinicguide.example', path: '/pain-relief/nephrotil', v: 'POTENTIAL_CONTRADICTION', p: 'critical', s: 'in_review', h: 9, title: 'Nephrotil: anticoagulant interaction claim contradicts FDA notice', ctx: 'Interactions › Common questions', claim: 'Nephrotil has no known interactions with blood thinners.', ch: 'no known interactions with blood thinners', ci: 1, eh: 'increases the risk of serious bleeding', why: 'A safety communication published after the page was last edited reports a bleeding interaction with anticoagulants. The page claim is now contradicted.', r: [0.9, 0.7, 0.9, 0.1] },
  { n: 1046, drug: 'cardio', site: 'clinicguide.example', path: '/heart/cardiolamine-dosing', v: 'INCOMPLETE_INFORMATION', p: 'high', s: 'open', h: 22, title: 'Cardiolamine: dose limit missing renal context', ctx: 'Dosing › Adults', claim: 'The maximum daily dose of Cardiolamine is 400 mg.', ch: '400 mg', ci: 1, eh: 'do not exceed 200 mg per day', why: 'The 400 mg limit is correct for normal renal function but the page omits the lower limit for severe renal impairment. Not wrong, but incomplete for a high-risk subgroup.', r: [0.75, 0.6, 0.85, 0.2] },
  { n: 1045, drug: 'gluc', site: 'pharmainfo-demo.example', path: '/diabetes/glucavane', v: 'POSSIBLY_OUTDATED', p: 'high', s: 'open', h: 30, title: 'Glucavane: starting dose may be outdated', ctx: 'Dosing › Getting started', claim: 'The recommended adult starting dose of Glucavane is 500 mg twice daily.', ch: '500 mg twice daily', ci: 1, eh: '500 mg once daily', why: 'The label was revised in July 2026 and the twice-daily start is no longer recommended. The page predates the revision.', r: [0.7, 0.55, 0.88, 0.12] },
  { n: 1044, drug: 'resp', site: 'testhealth.example', path: '/asthma/respirol-children', v: 'POTENTIAL_CONTRADICTION', p: 'high', s: 'awaiting_correction', h: 52, title: 'Respirol: pediatric age threshold mismatch', ctx: 'Children › Who can use it', claim: 'Respirol inhaler is suitable for children aged 4 and older.', ch: 'aged 4 and older', ci: 1, eh: '6 years of age and older', why: 'The label sets the minimum age at 6. The page gives 4.', r: [0.8, 0.65, 0.93, 0.07],
    dec: { decision: 'confirm', rationale: 'Age threshold is wrong versus the current label. Sent to the site owner for correction.', reviewer: 'Dr. Maya Rao', at: ago(20) } },
  { n: 1043, drug: 'derma', site: 'wellness-hub.example', path: '/skin/dermacalm', v: 'INCOMPLETE_INFORMATION', p: 'medium', s: 'resolved', h: 120, title: 'Dermacalm: application advice omits skin-integrity warning', ctx: 'How to use', claim: 'Apply Dermacalm cream freely to any affected area.', ch: 'any affected area', ci: 1, eh: 'Do not apply Dermacalm to broken or irritated skin', why: 'The label warns against use on broken skin. The page gives no such limit.', r: [0.45, 0.5, 0.85, 0.15],
    dec: { decision: 'confirm', rationale: 'Warning missing. Page corrected by site owner and verified by rescan.', reviewer: 'Dr. Maya Rao', at: ago(90) } },
  { n: 1042, drug: 'hep', site: 'pharmainfo-demo.example', path: '/vet/hepatrin-chews', v: 'POTENTIAL_CONTRADICTION', p: 'medium', s: 'dismissed', h: 160, title: 'Hepatrin: possible formulation mismatch (veterinary)', ctx: 'Pet health › Liver support', claim: 'Hepatrin Vet chewable is well tolerated in dogs with liver conditions.', ch: 'well tolerated in dogs with liver conditions', ci: 1, eh: 'contraindicated in patients with active liver disease', why: 'Matching is uncertain: the label covers the human tablet, while the claim names a veterinary chewable.', r: [0.4, 0.3, 0.45, 0.55],
    dec: { decision: 'dismiss', rationale: 'Claim refers to a veterinary product. The human-tablet label does not apply.', reviewer: 'Dr. Maya Rao', at: ago(140) } },
  { n: 1041, drug: 'lumixa', site: 'wellness-hub.example', path: '/sleep/lumixa', v: 'INSUFFICIENT_EVIDENCE', p: 'low', s: 'open', h: 70, title: 'Lumixa: geriatric safety claim lacks supporting evidence', ctx: 'Who can take it', claim: 'Lumixa is safe for adults over 75.', ch: 'safe for adults over 75', ci: 1, eh: 'did not include sufficient numbers', why: 'The label neither supports nor refutes safety in older adults. Marked for human review instead of guessing.', r: [0.5, 0.3, 0.25, 0.75] },
  { n: 1040, drug: 'zorv', site: 'wellness-hub.example', path: '/blood/zorvaxin-faq', v: 'POTENTIAL_CONTRADICTION', p: 'critical', s: 'open', h: 5, title: 'Zorvaxin: pregnancy continuation advice conflicts with contraindication', ctx: 'FAQ › Planning a pregnancy', claim: 'Zorvaxin may be continued during pregnancy at the usual dose.', ch: 'continued during pregnancy', ci: 1, eh: 'contraindicated in pregnant women', why: 'Same underlying FDA update as INC-1048, found on a second site.', r: [0.95, 0.6, 0.92, 0.08] },
]

const trace = (at) => [
  ['Discovery', 'Page change detected and snapshot stored'],
  ['Extraction', 'Claim extracted with clinical context'],
  ['Guideline Intelligence', 'Matched an FDA reference document'],
  ['Verification', 'Hybrid retrieval and context filters applied'],
  ['Contradiction', 'Rule checks and NLI comparison completed'],
  ['Risk Assessment', 'Priority computed from harm, exposure, evidence and uncertainty'],
  ['Alert', 'Incident created and reviewers notified'],
].map(([step, detail], i) => ({ step, detail, at: new Date(new Date(at).getTime() + i * 40e3).toISOString() }))

const incidents = seeds.map((s) => {
  const d = docs[s.doc || s.drug]
  const created = ago(s.h)
  const cs = s.claim.indexOf(s.ch)
  const ev = d.chunks[s.ci]
  const es = ev.text.indexOf(s.eh)
  return {
    id: `INC-${s.n}`, title: s.title, priority: s.p, verdict: s.v, status: s.s,
    site: s.site, page_url: `https://${s.site}${s.path}`, created_at: created,
    agent_run_id: `run_${(7400 + s.n).toString(16)}`,
    claim: { id: `clm_${s.n}`, statement: s.claim, context: s.ctx, offsets: [cs, cs + s.ch.length], snapshot_id: `snap_${s.n}`, snapshot_fetched_at: ago(s.h + 0.2), content_hash: hash(s.n) },
    evidence: [{ id: `evd_${s.n}`, document_id: d.id, authority: d.authority, doc_type: d.doc_type, title: d.title, version: d.version, effective_date: d.effective_date, url: d.url, section: ev.section, quote: ev.text, offsets: [es, es + s.eh.length] }],
    rationale: s.why,
    risk: { harm: s.r[0], exposure: s.r[1], evidence_strength: s.r[2], uncertainty: s.r[3] },
    decision: s.dec || null,
    trace: trace(created),
  }
})

const sites = [
  { id: 'site_1', domain: 'testhealth.example', jurisdiction: 'US', language: 'en', scan_interval_hours: 24, enabled: true, pages: 142, last_scan_at: ago(3), last_scan_status: 'completed' },
  { id: 'site_2', domain: 'clinicguide.example', jurisdiction: 'US', language: 'en', scan_interval_hours: 12, enabled: true, pages: 96, last_scan_at: ago(5), last_scan_status: 'completed' },
  { id: 'site_3', domain: 'pharmainfo-demo.example', jurisdiction: 'US', language: 'en', scan_interval_hours: 24, enabled: true, pages: 210, last_scan_at: ago(8), last_scan_status: 'failed' },
  { id: 'site_4', domain: 'wellness-hub.example', jurisdiction: 'US', language: 'en', scan_interval_hours: 48, enabled: true, pages: 58, last_scan_at: ago(30), last_scan_status: 'completed' },
  { id: 'site_5', domain: 'rxcorner.example', jurisdiction: 'US', language: 'en', scan_interval_hours: 168, enabled: false, pages: 37, last_scan_at: ago(400), last_scan_status: 'completed' },
]

const scans = sites.flatMap((s) =>
  [0, 1, 2, 3].map((k) => ({
    id: `scan_${s.id}_${k}`, site_id: s.id,
    status: s.last_scan_status === 'failed' && k === 0 ? 'failed' : 'completed',
    error: s.last_scan_status === 'failed' && k === 0 ? 'robots.txt disallowed the requested path' : null,
    started_at: ago(s.last_scan_at ? (Date.now() - new Date(s.last_scan_at)) / H + k * 24 : k * 24),
    pages_total: s.pages, pages_done: s.pages, changed: (k * 5 + 3) % 9, claims_extracted: (k * 7 + 4) % 15,
    duration_s: 41 + k * 9, trigger: k === 0 ? 'manual' : 'scheduled',
  }))
)

const users = [
  { id: 'u1', name: 'Sam Okafor', email: 'sam@medguard.example', role: 'admin', last_active: ago(1) },
  { id: 'u2', name: 'Dr. Maya Rao', email: 'maya@medguard.example', role: 'reviewer', last_active: ago(2) },
  { id: 'u3', name: 'Dr. Jonas Weber', email: 'jonas@medguard.example', role: 'reviewer', last_active: ago(26) },
  { id: 'u4', name: 'Lee Chen', email: 'lee@medguard.example', role: 'viewer', last_active: ago(70) },
]
let settings = {
  notifications: { email_enabled: true, recipients: 'review-team@medguard.example', webhook_url: '', min_priority: 'high', daily_digest: true },
  organization: { name: 'MedGuard Demo Org', default_scan_interval_hours: 24, jurisdictions: ['US'], retention_days: 365 },
}

const PRIO = { critical: 0, high: 1, medium: 2, low: 3 }
const ACTIVE = ['open', 'in_review', 'awaiting_correction']
const find = (id) => {
  const i = incidents.find((x) => x.id === id)
  if (!i) throw new Error('Incident not found')
  return i
}
const summary = (i) => ({
  id: i.id, title: i.title, priority: i.priority, verdict: i.verdict, status: i.status, site: i.site, page_url: i.page_url,
  claim_statement: i.claim.statement, evidence_authority: i.evidence[0].authority, evidence_date: i.evidence[0].effective_date, created_at: i.created_at,
})

function listIncidents(p = {}) {
  const q = (p.q || '').toLowerCase()
  return incidents
    .filter((i) =>
      (!p.priority || i.priority === p.priority) &&
      (!p.verdict || i.verdict === p.verdict) &&
      (!p.site || i.site === p.site) &&
      (!p.status || p.status === 'all' || (p.status === 'active' ? ACTIVE.includes(i.status) : i.status === p.status)) &&
      (!q || [i.title, i.claim.statement, i.site, i.id].some((t) => t.toLowerCase().includes(q)))
    )
    .sort((a, b) => PRIO[a.priority] - PRIO[b.priority] || new Date(b.created_at) - new Date(a.created_at))
    .map(summary)
}

function analytics() {
  const active = incidents.filter((i) => ACTIVE.includes(i.status))
  const by_priority = Object.fromEntries(Object.keys(PRIO).map((k) => [k, active.filter((i) => i.priority === k).length]))
  const scan_activity = Array.from({ length: 14 }, (_, i) => ({
    day: new Date(Date.now() - (13 - i) * 864e5).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    changed: 4 + ((i * 11) % 14), flagged: (i * 3) % 6,
  }))
  return {
    kpis: [
      { key: 'open', label: 'Open findings', value: active.length, delta: `${by_priority.critical} critical`, series: [3, 4, 4, 5, 6, 5, active.length] },
      { key: 'pages', label: 'Pages scanned (24h)', value: 1126, delta: '+3.2% vs yesterday', series: [90, 110, 95, 120, 130, 118, 126] },
      { key: 'claims', label: 'Claims verified', value: 2418, delta: '+64 this week', series: [20, 31, 28, 40, 36, 52, 64] },
      { key: 'review', label: 'Median time to review', value: '3.4h', delta: '0.6h faster this week', series: [5, 4.8, 4.2, 4, 3.9, 3.6, 3.4] },
    ],
    scan_activity,
    by_verdict: [
      { verdict: 'SUPPORTED', count: 2231 },
      { verdict: 'POTENTIAL_CONTRADICTION', count: 4 },
      { verdict: 'POSSIBLY_OUTDATED', count: 1 },
      { verdict: 'INCOMPLETE_INFORMATION', count: 2 },
      { verdict: 'INSUFFICIENT_EVIDENCE', count: 1 },
    ],
    by_priority,
    recent_runs: [
      { id: 'run_1d3a', site: 'testhealth.example', status: 'completed', pages: 142, changed: 6, at: ago(3), duration_s: 58 },
      { id: 'run_1d39', site: 'clinicguide.example', status: 'completed', pages: 96, changed: 3, at: ago(5), duration_s: 44 },
      { id: 'run_1d38', site: 'pharmainfo-demo.example', status: 'failed', pages: 0, changed: 0, at: ago(8), duration_s: 4, error: 'robots.txt disallowed path' },
      { id: 'run_1d37', site: 'wellness-hub.example', status: 'completed', pages: 58, changed: 2, at: ago(30), duration_s: 31 },
    ],
  }
}

function startScan({ site_id }) {
  const s = sites.find((x) => x.id === site_id)
  if (!s) throw new Error('Unknown site')
  if (!s.enabled) throw new Error('Enable this site before scanning')
  const sc = { id: `scan_${Date.now()}`, site_id, status: 'running', error: null, started_at: new Date().toISOString(), pages_total: s.pages, pages_done: 0, changed: 0, claims_extracted: 0, duration_s: 0, trigger: 'manual' }
  scans.unshift(sc)
  return sc
}
function getScan(id) {
  const sc = scans.find((x) => x.id === id)
  if (!sc) throw new Error('Scan not found')
  if (sc.status === 'running') {
    const f = Math.min(1, (Date.now() - new Date(sc.started_at)) / 6000)
    Object.assign(sc, { pages_done: Math.round(sc.pages_total * f), changed: Math.round(f * 4), claims_extracted: Math.round(f * 9), duration_s: Math.round(f * 6) })
    if (f >= 1) {
      sc.status = 'completed'
      Object.assign(sites.find((x) => x.id === sc.site_id), { last_scan_at: new Date().toISOString(), last_scan_status: 'completed' })
    }
  }
  return sc
}

function review(id, b) {
  const i = find(id)
  if (!b?.decision || (b.rationale || '').trim().length < 10) throw new Error('Choose a decision and write a rationale of at least 10 characters')
  const next = { confirm: 'awaiting_correction', dismiss: 'dismissed', needs_info: 'in_review' }
  i.status = next[b.decision]
  i.decision = { decision: b.decision, rationale: b.rationale.trim(), reviewer: 'Dr. Maya Rao', at: new Date().toISOString() }
  i.trace.push({ step: 'Human review', detail: `Reviewer decision recorded: ${b.decision}`, at: i.decision.at })
  return i
}
function recheck(id) {
  const i = find(id)
  if (i.status !== 'awaiting_correction') throw new Error('Recheck is only available after a confirmed issue has been corrected')
  i.status = 'resolved'
  i.trace.push({ step: 'Rescan', detail: 'Page rescanned. Claim no longer conflicts with the evidence.', at: new Date().toISOString() })
  return i
}

/* ---------- Org-wide audit log and in-app notifications ---------- */
const notifRead = new Set()
const REVIEW_LABEL = { confirm: 'Issue confirmed', needs_info: 'More information requested', dismiss: 'Dismissed as false alarm' }
const ADMIN_AUDIT = [
  { id: 'aud_set1', at: ago(26), actor: 'Sam Okafor', action: 'settings', object: 'Notification settings', detail: 'Alert threshold set to High priority and above' },
  { id: 'aud_role1', at: ago(74), actor: 'Sam Okafor', action: 'role', object: 'Dr. Jonas Weber', detail: 'Role changed to Clinical reviewer' },
  { id: 'aud_site1', at: ago(120), actor: 'Sam Okafor', action: 'site', object: 'rxcorner.example', site: 'rxcorner.example', detail: 'Monitoring paused (site disabled)' },
  { id: 'aud_site2', at: ago(300), actor: 'Sam Okafor', action: 'site', object: 'wellness-hub.example', site: 'wellness-hub.example', detail: 'Website added to monitoring' },
]
const domainOf = (siteId) => sites.find((x) => x.id === siteId)?.domain ?? siteId

function auditLog() {
  const ev = []
  for (const i of incidents) {
    if (i.decision) ev.push({ id: `aud_${i.id}`, at: i.decision.at, actor: i.decision.reviewer, action: 'review', object: i.id, incident_id: i.id, detail: `${REVIEW_LABEL[i.decision.decision]}: ${i.decision.rationale}` })
    if (i.status === 'resolved') ev.push({ id: `aud_${i.id}_re`, at: i.decision?.at ?? i.created_at, actor: 'Scan agent', action: 'recheck', object: i.id, incident_id: i.id, detail: 'Page rescanned — the claim no longer conflicts with the evidence' })
  }
  for (const s of scans) {
    if (s.status === 'failed') ev.push({ id: `aud_${s.id}`, at: s.started_at, actor: 'Scan agent', action: 'scan', object: domainOf(s.site_id), site: domainOf(s.site_id), detail: `Scan failed — ${s.error}` })
  }
  return ev.concat(ADMIN_AUDIT).sort((a, b) => new Date(b.at) - new Date(a.at))
}

function notifications() {
  const out = []
  for (const i of incidents) {
    if (ACTIVE.includes(i.status) && (i.priority === 'critical' || i.priority === 'high'))
      out.push({ id: `ntf_${i.id}`, kind: 'finding', tone: i.priority, title: `New ${i.priority} finding on ${i.site}`, detail: i.title, at: i.created_at, href: `/incidents/${i.id}` })
    if (i.status === 'resolved')
      out.push({ id: `ntf_${i.id}_res`, kind: 'resolved', title: `Finding resolved on ${i.site}`, detail: i.title, at: i.decision?.at ?? i.created_at, href: `/incidents/${i.id}` })
  }
  for (const s of scans) {
    if (s.status === 'failed')
      out.push({ id: `ntf_${s.id}`, kind: 'scan_failed', title: `Scan failed on ${domainOf(s.site_id)}`, detail: s.error, at: s.started_at, href: `/sites/${s.site_id}` })
  }
  return out.sort((a, b) => new Date(b.at) - new Date(a.at)).map((n) => ({ ...n, read: notifRead.has(n.id) }))
}

export async function mockRequest(method, path, params = {}, body) {
  await sleep(200 + Math.random() * 250)
  let m
  if (path === '/analytics/summary') return clone(analytics())
  if (path === '/sites') {
    if (method === 'GET') return clone(sites)
    const domain = (body?.domain || '').trim().toLowerCase()
    if (sites.some((s) => s.domain === domain)) throw new Error('That domain is already registered')
    const s = { id: `site_${Date.now()}`, domain, jurisdiction: body.jurisdiction || 'US', language: 'en', scan_interval_hours: Number(body.scan_interval_hours) || 24, enabled: true, pages: 0, last_scan_at: null, last_scan_status: null }
    sites.push(s)
    return clone(s)
  }
  if ((m = path.match(/^\/sites\/([^/]+)$/))) {
    const s = sites.find((x) => x.id === m[1])
    if (!s) throw new Error('Site not found')
    if (method === 'PATCH') Object.assign(s, body)
    return clone(s)
  }
  if (path === '/scans') {
    if (method === 'POST') return clone(startScan(body))
    return clone(scans.filter((s) => !params.site_id || s.site_id === params.site_id).sort((a, b) => new Date(b.started_at) - new Date(a.started_at)))
  }
  if ((m = path.match(/^\/scans\/([^/]+)$/))) return clone(getScan(m[1]))
  if (path === '/claims') {
    const q = (params.q || '').toLowerCase()
    return clone(incidents.filter((i) => !q || i.claim.statement.toLowerCase().includes(q)).map((i) => ({ ...i.claim, site: i.site, page_url: i.page_url, incident_id: i.id })))
  }
  if (path === '/incidents') return clone(listIncidents(params))
  if ((m = path.match(/^\/incidents\/([^/]+)\/review$/)) && method === 'POST') return clone(review(m[1], body))
  if ((m = path.match(/^\/incidents\/([^/]+)\/recheck$/)) && method === 'POST') return clone(recheck(m[1]))
  if ((m = path.match(/^\/incidents\/([^/]+)$/))) return clone(find(m[1]))
  if (path === '/references') {
    const q = (params.q || '').toLowerCase()
    return clone(Object.values(docs).filter((d) => !q || d.title.toLowerCase().includes(q) || d.chunks.some((c) => c.text.toLowerCase().includes(q))))
  }
  if (path === '/admin/users') return clone(users)
  if ((m = path.match(/^\/admin\/users\/([^/]+)$/)) && method === 'PATCH') {
    const u = users.find((x) => x.id === m[1])
    Object.assign(u, body)
    return clone(u)
  }
  if (path === '/admin/settings') {
    if (method === 'PUT') settings = { ...settings, ...body }
    return clone(settings)
  }
  if (path === '/audit') return clone(auditLog())
  if (path === '/notifications') return clone(notifications())
  if (path === '/notifications/read-all') { notifications().forEach((n) => notifRead.add(n.id)); return { ok: true } }
  if ((m = path.match(/^\/notifications\/([^/]+)\/read$/))) { notifRead.add(m[1]); return { ok: true } }
  throw new Error(`Mock API has no handler for ${method} ${path}`)
}
