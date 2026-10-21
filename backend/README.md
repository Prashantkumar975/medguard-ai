# MedGuard AI — Backend

Open-source AI healthcare website auditing and monitoring platform. This document
covers the Python backend: setup, API, model configuration, deployment, testing and
benchmarking.

> **Not a clinical decision system.** MedGuard flags *potential* content
> discrepancies for human review. It never certifies medical advice as safe or
> unsafe. Potentially harmful findings require expert review.

## Architecture

- **FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic** — API, models, migrations.
- **PostgreSQL + pgvector** — persistence and hybrid vector/keyword evidence retrieval.
- **Redis + Celery (+ Beat)** — background investigations and recurring scans.
- **LangGraph** — stateful investigation workflow (crawl → extract → retrieve →
  verify → risk → incident → human review), with persisted `agent_runs`.
- **Ollama + Qwen** (local dev) / **vLLM** (optional prod) — open-weight inference.
- **fastembed (BAAI/bge-small-en-v1.5)** — CPU-friendly embeddings (ONNX).
- **HTTPX + Trafilatura + BeautifulSoup4 (+ optional Playwright)** — crawling and
  content extraction.

Deterministic code handles crawling, hashing, permissions, structured checks and
risk scoring. The LLM is used only for claim extraction and semantic comparison —
never to fabricate evidence or citations.

## Quick start (local, no Docker)

Requires Python 3.12+, PostgreSQL 16 + pgvector, Redis, and Ollama.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env .env.local        # edit DATABASE_URL / REDIS_URL / OLLAMA_BASE_URL
alembic upgrade head      # create schema
python -m scripts.bootstrap          # org + admin user
python -m scripts.seed_references    # fictional knowledge base + embeddings

uvicorn app.main:app --reload --port 8000
# in other shells:
celery -A app.workers.celery_app.celery_app worker --loglevel=info
celery -A app.workers.celery_app.celery_app beat --loglevel=info
```

Default admin (from `.env`): `admin@medguard.local` / `ChangeMe123!`.

### Demo end-to-end

```bash
python -m http.server 8090 --directory scripts/demo_site   # fictional site
# register http://127.0.0.1:8090 as a site (ALLOW_LOCAL_TARGETS=true in .env for
# loopback crawling — never enable in production), then POST /api/v1/scans.
```

## Deployment (Docker Compose)

```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.bootstrap
docker compose exec api python -m scripts.seed_references
```

Services: `db` (pgvector/pg16), `redis`, `api`, `worker`, `beat`, `ollama`.
Postgres/Redis/Ollama ports are **not** published to the public network by default
(Ollama is loopback-only). Set a strong `SECRET_KEY` in production.

### Model setup

Local dev uses Ollama. Pull the model once:

```bash
ollama pull qwen2.5:1.5b       # ~1 GB, CPU-friendly default
# or a larger model for higher quality:
ollama pull qwen2.5:7b
```

Model ID and license: `qwen2.5:1.5b` (Apache-2.0). Point `OLLAMA_BASE_URL` /
`OLLAMA_MODEL` at a vLLM OpenAI-compatible server for production inference — no
paid proprietary API is required.

CPU-only works (slower). For GPU acceleration, run Ollama or vLLM with CUDA and
set `OLLAMA_BASE_URL` accordingly; the backend is agnostic to the inference host.

## Configuration

All settings are environment-driven (`app/core/config.py`). Key variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `DATABASE_URL` | Postgres DSN (pgvector) | `postgresql+psycopg://…/medguard` |
| `REDIS_URL` | Celery broker/backend | `redis://127.0.0.1:6379/0` |
| `SECRET_KEY` | JWT signing (≥32 bytes) | dev default — override! |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | inference host / model | Ollama / qwen2.5:1.5b |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | embedding model | bge-small-en-v1.5 / 384 |
| `ALLOW_LOCAL_TARGETS` | permit loopback crawl (dev only) | `false` |
| `CRAWL_MAX_PAGES_PER_SCAN` | per-scan page budget | 25 |
| `LOGIN_RATE_LIMIT_*` | login throttling | on / 5 per 60s |

## API

All routes under `/api/v1`. Interactive docs at `/docs`. Auth uses
`Authorization: Bearer <access_token>`; tokens come from `POST /auth/login`.

### Auth
- `POST /auth/login` `{email, password}` → `{access_token, refresh_token}`
- `POST /auth/refresh` `{refresh_token}` → rotated pair (old token revoked)
- `POST /auth/logout` `{refresh_token}`
- `GET /auth/me` → `{id, name, email, role, organization_id}`

### Health
- `GET /health` → liveness. `GET /health/ready` → DB/Redis/model readiness.

### Sites & scans
- `GET /sites` · `POST /sites` `{domain, jurisdiction?, language?, scan_interval_hours?}`
- `GET /sites/{id}` · `PATCH /sites/{id}` `{enabled, …}`
- `POST /scans` `{site_id}` → enqueues a Celery job, returns a real `Scan`
- `GET /scans?site_id=` · `GET /scans/{id}` → live progress

### Claims, incidents, references
- `GET /claims?q=`
- `GET /incidents?q,&priority,&verdict,&site,&status` → summaries
- `GET /incidents/{id}` → full detail (claim, evidence, risk, trace)
- `POST /incidents/{id}/review` `{decision, rationale}` — `rationale` ≥ 10 chars;
  `confirm → awaiting_correction`, `dismiss → dismissed`, `needs_info → in_review`
- `POST /incidents/{id}/recheck` — only from `awaiting_correction`; enqueues a
  re-crawl and retains prior history as a new attempt
- `GET /references?q=`

### Analytics, admin, notifications, reports
- `GET /analytics/summary` → KPIs, scan activity, verdict/priority distribution, runs
- `GET /admin/users` · `PATCH /admin/users/{id}` `{role}`
- `GET /admin/settings` · `PUT /admin/settings`
- `GET /audit` · `GET /notifications` · `POST /notifications/{id}/read` · `POST /notifications/read-all`
- `GET /reports/{incident_id}/pdf` → downloadable audit report

### Permissions
`admin` full · `reviewer` scan+review · `viewer` read-only. Enforced server-side
per endpoint (`app/api/deps.py`); the frontend derives `can()` from `GET /auth/me`.

## Verdicts

`SUPPORTED` · `POTENTIAL_CONTRADICTION` · `POSSIBLY_OUTDATED` ·
`INCOMPLETE_INFORMATION` · `INSUFFICIENT_EVIDENCE`. Structured checks (medication,
formulation, dose, population, species, jurisdiction, recency, numeric conflict)
run **before** the semantic comparison. Lack of evidence is never treated as
contradiction; citations must point to real ingested passages.

## Testing

```bash
pytest app/tests -q
```

Runs against a real Postgres test DB (`medguard_test`, auto-created). Covers auth,
RBAC, tenant isolation, CRUD, the incident lifecycle, SSRF protection, extraction
schema, the risk engine, verdict routing, and adversarial prompt-injection. Tests
requiring the live model are skipped when Ollama is unreachable (never mocked).
The login rate limiter is disabled for the suite and proven in a dedicated test.

## Benchmarking

```bash
python -m scripts.benchmark          # deterministic + retrieval + memory
python -m scripts.benchmark --full   # adds live-model extraction P/R/F1 + latency
```

Results go to `docs/BENCHMARK_RESULTS.md`, separating **measured** numbers from
targets. The eval set is fictional (invented drugs) and is **not** a clinical
validation claim.
