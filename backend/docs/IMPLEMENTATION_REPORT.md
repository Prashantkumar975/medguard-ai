# MedGuard AI — Final Implementation Report

Date: 2026-10-19 · Scope: full backend build per the Master Implementation Prompt,
integrated with the existing React frontend without replacing it.

---

## 1. Completed functionality

### Phase 1 — Repository audit & API contract
- `docs/API_CONTRACT.md`: all 22 frontend endpoints mapped to request/response
  schemas derived from `frontend/src/api/mock.js`, the permission model, every
  behavioral rule the mock enforces (exact error strings, state transitions,
  filter/sort semantics), and the six gaps between the mock and the brief.

### Phase 2 — Foundation
- FastAPI app (`app/main.py`), settings (`app/core/config.py`), SQLAlchemy 2.x
  models for all 19 entities (`app/models/entities.py`), Alembic migration
  (`alembic/versions/…initial_schema`), JWT auth with **rotating refresh tokens**
  (hashed at rest, rotation revokes predecessors), bcrypt password hashing,
  Redis-backed login rate limiting, RBAC dependencies, org-scoped queries
  everywhere.

### Phase 3 — Frontend API contract
- Every endpoint under `/api/v1`, returning the exact shapes the UI expects
  (bare arrays, no envelopes), with the contract's error strings
  (`"That domain is already registered"`, `"Choose a decision and write a rationale
  of at least 10 characters"`, etc.) and its filter/sort semantics.

### Phase 4 — Crawling engine
- Sitemap + bounded link discovery, robots.txt with crawl-delay, SSRF guard
  (scheme/port allow-lists, private/loopback/link-local rejection with explicit
  dev-only opt-in, per-hop redirect revalidation, size caps, timeouts, budgets),
  Trafilatura extraction with BS4 fallback, SHA-256 hashing, versioned snapshots,
  change detection (unchanged pages skipped).

### Phase 5 — Claim extraction
- Real Qwen (`qwen2.5:1.5b` via Ollama, Apache-2.0) with JSON-mode output,
  Pydantic schema validation, verbatim-offset anchoring against source text,
  bounded retries, structured failure records. Invalid JSON / hallucinated
  offsets are rejected, never silently accepted (the live demo run rejected one
  bad Qwen output for this reason).

### Phase 6 — Evidence retrieval
- Versioned knowledge base, sentence-aware chunking, fastembed
  (BAAI/bge-small-en-v1.5) vectors in pgvector, hybrid search (vector + keyword
  with reciprocal-rank fusion), jurisdiction filtering, and citation validation
  (every citation must be a verbatim substring of a stored chunk).

### Phase 7 — Verification workflow + risk
- LangGraph workflow (`app/agents/workflow.py`) with persisted `agent_runs`.
  Deterministic structured checks run **before** the LLM comparison: medication
  identity, formulation, dosage, population, species (veterinary vs human guard),
  jurisdiction, recency, and a numeric/frequency conflict guard. All five verdicts
  supported; absence of evidence routes to `INSUFFICIENT_EVIDENCE`, never to
  contradiction. Deterministic risk engine documented in `docs/RISK_ENGINE.md`.

### Phase 8 — Background jobs + incidents
- Celery tasks (scan, recheck, scheduled scans via Beat) with retries/backoff,
  idempotent per scan, progress persisted to the `scans` table. Full incident
  lifecycle (5 states, 3 decisions, immutable `reviews` audit rows, trace
  entries), dedupe by source+claim+evidence identity, recheck enqueues a real
  re-crawl as a **new attempt** retaining history.

### Phase 9 — Frontend integration
- `AuthContext.jsx` rewritten: real session from `GET /auth/me`, `login/logout`,
  role derived from the server (localStorage escalation removed), auto token
  refresh in `client.js`, new `/login` route + `RequireAuth` guard, sidebar sign
  out. Mock mode still works untouched. Frontend builds cleanly.

### Phase 10 — Tests, Docker, benchmark, docs
- **47 tests passing** against a real Postgres+pgvector test DB: auth, refresh
  rotation, RBAC, tenant isolation, CRUD, incident lifecycle (exact contract
  messages), SSRF, extraction schema, risk engine, verdict routing, adversarial
  prompt injection, rate-limiter proof.
- `docker-compose.yml` (db/redis/api/worker/beat/ollama + optional frontend),
  backend `Dockerfile`, `.env.example`-style `.env`.
- `scripts/benchmark.py` → `docs/BENCHMARK_RESULTS.md`.
- `backend/README.md` (API reference + deployment), `docs/RISK_ENGINE.md`.

---

## 2. Verified end-to-end demo (executed, not simulated)

1. PostgreSQL 18.6 + pgvector 0.8.7, Redis, Ollama all running locally; migrations
   applied (20 tables).
2. Admin bootstrapped; 7 **clearly-labeled fictional** reference documents ingested
   with real embeddings.
3. Local demo healthcare site served on `127.0.0.1:8090`, registered through the API.
4. `POST /scans` → real Celery job → 6 pages crawled/snapshotted → Qwen extracted
   claims → pgvector hybrid retrieval → verification → **INC-1001/1002/1003
   persisted** (two `POTENTIAL_CONTRADICTION`, one `SUPPORTED`) with evidence
   citations, risk components, and 11-step investigation traces.
5. Reviewer decisions, recheck gating, analytics, and PDF report endpoint all
   exercised through the API.

**Measured benchmark** (`--full`, live model): extraction precision/recall/F1 =
1.0 / 1.0 / 1.0 (3 TP, 0 FP, 0 FN), latency p50 1.93 s / p95 2.00 s; retrieval
Recall@1/3/5 = 1.0; unsupported-citation rate = 0; numeric-guard accuracy = 1.0;
model resident memory 1367 MB. Eval set is fictional — **not** clinical validation.

**Real bugs found and fixed by running things** (not by inspection):
httpx streamed-read misuse in the crawler; Redis RESP3/kombu incompatibility
(pinned redis-py 5.x); ingestion unpack error; exposure formula inflating
1-page sites; quantity-normalizer key mismatch dropping age conflicts; missing
frequency-word matching ("twice daily"); missing offset-order validator;
rate limiter throttling the test suite (now toggleable, still tested).

---

## 3. Tests executed

`pytest app/tests -q` → **47 passed** (real DB, real FastAPI app). Benchmark
script executed twice (offline and `--full`). Frontend `npm run build` → exit 0.
API smoke tests executed live against the running server (login, RBAC, CRUD,
scans, incidents, health/ready all green).

## 4. Remaining limitations (honest)

1. **Docker Compose authored but not executed** — this Windows host has no Docker
   daemon, so `docker compose up` could not be run here. Compose files follow the
   standard pgvector/redis patterns but are unverified on this machine.
2. **Environment-specific process management** — services (Postgres, Redis,
   Ollama, Celery, uvicorn) were started manually on this host; production should
   run them under the compose stack or a process supervisor.
3. **Playwright JS rendering** — code path present and configurable
   (`JS_RENDER_ENABLED`), browser binary not installed in this environment; the
   demo site is server-rendered so it was never needed.
4. **openFDA/WHO/CDC live ingestion** — the ingestion framework ships with the
   fictional corpus; wiring live government APIs (and honoring their rate limits
   and licenses) is scaffolded but not exercised against production endpoints.
5. **qwen2.5:1.5b quality** — chosen for CPU feasibility. It missed one numeric
   conflict on its own (caught afterward by the deterministic guard); larger
   Qwen models will improve semantic accuracy. Benchmark numbers are from a
   4-case fictional set — indicative, not statistically strong.
6. **Email/webhook notification delivery** — notification records are created and
   surfaced in-app; outbound email/webhook transport is configuration-only stubs
   by design (no mail server in scope).
7. **Root/repo duplication** — the repo's root-level `index.html`/`vite.config.js`
   copy without `src/` predates this work and was left untouched.
