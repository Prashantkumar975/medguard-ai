# MedGuard AI — Frontend API Contract (Phase 1 Audit)

Source of truth: `frontend/src/api/mock.js` (response shapes), `frontend/src/api/endpoints.js`
(route list), `frontend/src/api/client.js` (transport + auth), `frontend/src/auth/AuthContext.jsx`
(permission model), `frontend/src/lib/constants.js` (enum labels/tones).

The mock module is the contract. Every shape below is what the real API must return.
All routes are prefixed `/api/v1`. The frontend sends
`Authorization: Bearer <localStorage.mg_token>` when a token exists.

---

## 1. Transport and error semantics

| Aspect | Frontend expectation |
| --- | --- |
| Base URL | `{VITE_API_URL}/api/v1` |
| Auth header | `Authorization: Bearer <mg_token>` (only when token present) |
| Content type | `application/json` |
| Success | JSON body; `204` handled as `null` |
| Failure | Non-2xx → body must contain `detail`; frontend throws `Error(detail)` |
| Unknown route | Mock throws `Mock API has no handler for {method} {path}` |

**Contract note:** the frontend has no retry, no pagination cursor handling, and no
loading-envelope. Endpoints must return plain arrays/objects, not `{data, meta}` wrappers.

---

## 2. Permission model (from `AuthContext.jsx`)

```
PERMS = {
  review:       ['admin', 'reviewer'],
  scan:         ['admin', 'reviewer'],
  manageSites:  ['admin'],
  administer:   ['admin'],
}
```

| Role | review | scan | manageSites | administer |
| --- | --- | --- | --- | --- |
| admin | yes | yes | yes | yes |
| reviewer | yes | yes | no | no |
| viewer | no | no | no | no |

**Security gap to fix (mandated by the brief):** the role is currently read from
`localStorage.getItem('mg_role')`, so a viewer can escalate by editing localStorage. The
backend must derive the role from the JWT and the frontend must derive `can()` from
`GET /auth/me`, never from localStorage.

`RequirePerm` renders an access-denied card when `can(perm)` is false; it does not issue a
request. Backend enforcement is therefore still required per endpoint.

---

## 3. Endpoint compatibility matrix

Legend for "Backend": the implementation module this maps to.

| # | Frontend caller | Method + path | Request | Expected response | Permission | Backend |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `api.analytics` | `GET /analytics/summary` | – | `AnalyticsSummary` | viewer | `api/v1/analytics.py` |
| 2 | `api.sites` | `GET /sites` | – | `Site[]` | viewer | `api/v1/sites.py` |
| 3 | `api.addSite` | `POST /sites` | `{domain, jurisdiction?, language?, scan_interval_hours?}` | `Site` | manageSites | `api/v1/sites.py` |
| 4 | `api.updateSite` | `PATCH /sites/{id}` | partial `Site` (`enabled` in UI) | `Site` | manageSites | `api/v1/sites.py` |
| 5 | `api.site` | `GET /sites/{id}` | – | `Site` | viewer | `api/v1/sites.py` |
| 6 | `api.startScan` | `POST /scans` | `{site_id}` | `Scan` (immediately, status `queued`/`running`) | scan | `api/v1/scans.py` |
| 7 | `api.scans` | `GET /scans` | `site_id?` | `Scan[]` newest first | viewer | `api/v1/scans.py` |
| 8 | `api.scan` | `GET /scans/{id}` | – | `Scan` with live progress | viewer | `api/v1/scans.py` |
| 9 | `api.claims` | `GET /claims` | `q?` | `Claim[]` | viewer | `api/v1/claims.py` |
| 10 | `api.incidents` | `GET /incidents` | `q?, priority?, verdict?, site?, status?` | `IncidentSummary[]` | viewer | `api/v1/incidents.py` |
| 11 | `api.incident` | `GET /incidents/{id}` | – | `IncidentDetail` | viewer | `api/v1/incidents.py` |
| 12 | `api.review` | `POST /incidents/{id}/review` | `{decision, rationale}` | `IncidentDetail` | review | `api/v1/incidents.py` |
| 13 | `api.recheck` | `POST /incidents/{id}/recheck` | – | `IncidentDetail` | review | `api/v1/incidents.py` |
| 14 | `api.references` | `GET /references` | `q?` | `ReferenceDoc[]` | viewer | `api/v1/references.py` |
| 15 | `api.users` | `GET /admin/users` | – | `User[]` | administer | `api/v1/admin.py` |
| 16 | `api.updateUser` | `PATCH /admin/users/{id}` | `{role}` | `User` | administer | `api/v1/admin.py` |
| 17 | `api.settings` | `GET /admin/settings` | – | `Settings` | administer | `api/v1/admin.py` |
| 18 | `api.saveSettings` | `PUT /admin/settings` | partial `Settings` | `Settings` | administer | `api/v1/admin.py` |
| 19 | `api.audit` | `GET /audit` | – | `AuditEvent[]` | administer | `api/v1/admin.py` |
| 20 | `api.notifications` | `GET /notifications` | – | `Notification[]` | viewer | `api/v1/notifications.py` |
| 21 | `api.markNotificationRead` | `POST /notifications/{id}/read` | – | `{ok: true}` | viewer | `api/v1/notifications.py` |
| 22 | `api.markAllNotificationsRead` | `POST /notifications/read-all` | – | `{ok: true}` | viewer | `api/v1/notifications.py` |

### Endpoints required by the brief but absent from the frontend today

| Method + path | Purpose | Permission |
| --- | --- | --- |
| `POST /auth/login` | issue access + refresh token | public |
| `POST /auth/refresh` | rotate refresh token | refresh token |
| `POST /auth/logout` | revoke refresh token | authenticated |
| `GET /auth/me` | real identity + role for `AuthProvider` | authenticated |
| `GET /health` | liveness | public |
| `GET /health/ready` | readiness (DB, Redis, model) | public |
| `GET /reports/{incident_id}/pdf` | PDF audit report | viewer |

---

## 4. Schemas

### 4.1 `Site`
```json
{
  "id": "site_1", "domain": "testhealth.example", "jurisdiction": "US",
  "language": "en", "scan_interval_hours": 24, "enabled": true,
  "pages": 142, "last_scan_at": "ISO-8601|null", "last_scan_status": "completed|failed|running|queued|null"
}
```
IDs are opaque strings in mock; the real backend may use UUIDs — the frontend only uses them
in route params and equality checks, so any stable string is compatible.

### 4.2 `Scan`
```json
{
  "id": "scan_...", "site_id": "site_1",
  "status": "queued|running|completed|failed|cancelled",
  "error": "string|null", "started_at": "ISO-8601",
  "pages_total": 142, "pages_done": 61, "changed": 3, "claims_extracted": 8,
  "duration_s": 24, "trigger": "manual|scheduled"
}
```

### 4.3 `IncidentSummary` (list row)
```json
{
  "id": "INC-1048", "title": "string", "priority": "critical|high|medium|low",
  "verdict": "SUPPORTED|POTENTIAL_CONTRADICTION|POSSIBLY_OUTDATED|INCOMPLETE_INFORMATION|INSUFFICIENT_EVIDENCE",
  "status": "open|in_review|awaiting_correction|resolved|dismissed",
  "site": "testhealth.example", "page_url": "https://...",
  "claim_statement": "string", "evidence_authority": "FDA", "evidence_date": "YYYY-MM-DD",
  "created_at": "ISO-8601"
}
```

### 4.4 `IncidentDetail`
```json
{
  "id": "INC-1048", "title": "string", "priority": "critical",
  "verdict": "POTENTIAL_CONTRADICTION", "status": "open",
  "site": "testhealth.example", "page_url": "https://...", "created_at": "ISO-8601",
  "agent_run_id": "run_1d3a",
  "claim": {
    "id": "clm_1048", "statement": "string", "context": "Patient FAQ › Special populations",
    "offsets": [12, 45], "snapshot_id": "snap_1048",
    "snapshot_fetched_at": "ISO-8601", "content_hash": "sha256:..."
  },
  "evidence": [
    {
      "id": "evd_1048", "document_id": "ref_zorv", "authority": "FDA",
      "doc_type": "Drug Safety Communication", "title": "string", "version": "v2",
      "effective_date": "2026-08-21", "url": "https://...", "section": "Contraindications",
      "quote": "string", "offsets": [10, 42]
    }
  ],
  "rationale": "string",
  "risk": { "harm": 0.95, "exposure": 0.8, "evidence_strength": 0.92, "uncertainty": 0.08 },
  "decision": { "decision": "confirm", "rationale": "string", "reviewer": "Dr. Maya Rao", "at": "ISO-8601" } | null,
  "trace": [ { "step": "Discovery", "detail": "string", "at": "ISO-8601" } ]
}
```
`offsets` are `[start, end]` character offsets into `claim.statement` / `evidence[].quote`
respectively. The backend must validate these against the stored source text.

### 4.5 `Claim` (from `GET /claims`)
`IncidentDetail.claim` plus `"site"`, `"page_url"`, `"incident_id"`.

### 4.6 `ReferenceDoc`
```json
{
  "id": "ref_zorv", "authority": "FDA", "doc_type": "Drug Safety Communication",
  "title": "string", "version": "v2", "effective_date": "2026-08-21",
  "url": "https://...", "identifiers": { "Application": "NDA 999001" },
  "chunks": [ { "section": "Summary", "text": "string" } ]
}
```

### 4.7 `User`
```json
{ "id": "u1", "name": "Sam Okafor", "email": "sam@medguard.example", "role": "admin|reviewer|viewer", "last_active": "ISO-8601" }
```
No `password_hash` or `organization_id` may be exposed.

### 4.8 `Settings`
```json
{
  "notifications": { "email_enabled": true, "recipients": "string", "webhook_url": "string",
                     "min_priority": "critical|high|medium|low", "daily_digest": true },
  "organization": { "name": "string", "default_scan_interval_hours": 24,
                    "jurisdictions": ["US"], "retention_days": 365 }
}
```

### 4.9 `AnalyticsSummary`
```json
{
  "kpis": [ { "key": "open|pages|claims|review", "label": "string",
              "value": 7, "delta": "string", "series": [3, 4, 4, 5, 6, 5, 7] } ],
  "scan_activity": [ { "day": "Oct 5", "changed": 4, "flagged": 2 } ],
  "by_verdict": [ { "verdict": "SUPPORTED", "count": 2231 } ],
  "by_priority": { "critical": 3, "high": 3, "medium": 0, "low": 1 },
  "recent_runs": [ { "id": "run_1d3a", "site": "string", "status": "completed",
                     "pages": 142, "changed": 6, "at": "ISO-8601",
                     "duration_s": 58, "error": "string|null" } ]
}
```
`Dashboard.jsx` resolves the headline figure with `kpis.find(k => k.key === 'open')`, so every
`key` referenced by the UI (`open`, `pages`, `claims`, `review`) **must** be present. The array
order only controls card display order; the four-card grid falls back to four placeholders when
`kpis` is absent, so returning an empty array renders empty cards rather than crashing.

### 4.10 `AuditEvent`
```json
{ "id": "aud_1", "at": "ISO-8601", "actor": "string", "action": "review|recheck|scan|site|role|settings",
  "object": "string", "incident_id": "INC-1048?", "site": "domain?", "detail": "string" }
```
Sorted newest first.

### 4.11 `Notification`
```json
{ "id": "ntf_1", "kind": "finding|resolved|scan_failed", "tone": "critical|high?",
  "title": "string", "detail": "string", "at": "ISO-8601", "href": "/incidents/INC-1048", "read": false }
```

---

## 5. Behavioural rules the backend must reproduce

These are enforced in the mock and are therefore part of the contract.

### `POST /incidents/{id}/review`
- Reject when `decision` missing or `rationale.trim().length < 10`
  → error text: `Choose a decision and write a rationale of at least 10 characters`
- State transition: `confirm → awaiting_correction`, `dismiss → dismissed`, `needs_info → in_review`
- Appends a `Human review` trace entry

### `POST /incidents/{id}/recheck`
- Only valid when `status === 'awaiting_correction'`
  → error text: `Recheck is only available after a confirmed issue has been corrected`
- Transition: `awaiting_correction → resolved`
- Appends a `Rescan` trace entry
- **Brief requirement beyond mock:** must enqueue a real re-crawl and retain the prior
  incident history rather than mutating in place.

### `POST /sites`
- Duplicate domain → `That domain is already registered`
- Defaults: `jurisdiction: 'US'`, `language: 'en'`, `scan_interval_hours: 24`, `enabled: true`,
  `pages: 0`, `last_scan_at: null`, `last_scan_status: null`

### `PATCH /sites/{id}`
- Unknown id → `Site not found`
- Shallow-merges the body (UI sends `{enabled: false}`)

### `POST /scans`
- Unknown site → `Unknown site`
- Disabled site → `Enable this site before scanning`
- Returns a real `Scan` record immediately (`status: 'running'` in mock); per the brief the real
  backend must enqueue a Celery job and return `queued`/`running` with live progress from `GET /scans/{id}`

### `GET /incidents` filtering
- `q` — case-insensitive substring over `title`, `claim.statement`, `site`, `id`
- `priority`, `verdict`, `site` — exact match
- `status` — `all` (no filter), `active` (`open|in_review|awaiting_correction`), else exact match
- Sort: priority rank `critical(0) < high(1) < medium(2) < low(3)`, then `created_at` desc

### `GET /claims`
- `q` — case-insensitive substring over `claim.statement`
- Returns claim objects enriched with `site`, `page_url`, `incident_id`

### `GET /references`
- `q` — case-insensitive substring over `title` **or any `chunk.text`**

### `GET /admin/users` / `PATCH /admin/users/{id}`
- PATCH shallow-merges (UI sends `{role}`)

### `GET /audit`
Union of: incident review decisions, resolved-recheck events, failed scans, and admin
settings/role/site changes — sorted newest first.

### `GET /notifications`
- finding: active status **and** priority `critical` or `high`
- resolved: status `resolved`
- scan_failed: scan `status === 'failed'`
- sorted newest first

---

## 6. Gaps between the mock contract and the brief

| Gap | Detail | Resolution |
| --- | --- | --- |
| No auth endpoints | `endpoints.js` has no `/auth/*`; `AuthContext` is simulated | Add `/auth/login|refresh|logout|me`, rewrite `AuthProvider` to fetch `/auth/me` |
| Role from localStorage | Privilege escalation vector | Derive role from JWT; `can()` from server claims |
| Flat arrays, no pagination | Brief demands pagination | Add optional `?page=&page_size=` returning the same bare array when absent |
| No PDF route | Brief requires `GET /reports/{incident_id}/pdf` | Add; not referenced by current UI |
| `recheck` mutates in place | Brief requires new investigation attempt retaining history | Add `recheck_of` / attempt history |
| IDs are opaque strings | Mock uses `site_1` / `INC-1048` | Real UUIDs are compatible; UI only echoes them |

---

## 7. Enumerations (from `lib/constants.js`)

```
VERDICTS  : SUPPORTED | POTENTIAL_CONTRADICTION | POSSIBLY_OUTDATED | INCOMPLETE_INFORMATION | INSUFFICIENT_EVIDENCE
PRIORITIES: critical | high | medium | low
STATUSES  : open | in_review | awaiting_correction | resolved | dismissed
DECISIONS : confirm | needs_info | dismiss
```
