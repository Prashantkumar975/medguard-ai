# MedGuard AI Implementation Notes

## Project scope

MedGuard AI is a research and demonstration tool for monitoring approved websites and comparing extracted medical claims with organization-provided reference documents. It creates findings for human review. It is not a clinical decision system, and the bundled sample corpus is fictional.

## Implemented components

- FastAPI backend, React frontend, PostgreSQL with pgvector, Redis, Celery, and Celery Beat.
- Nebius Token Factory OpenAI-compatible model integration by default, with Ollama available for local development.
- Website crawling with robots handling, bounded page budgets, redirect validation, DNS-pinned requests, and page snapshots.
- Claim extraction, keyword and vector retrieval, evidence-linked verification, deterministic triage scoring, and incident review workflows.
- Organization-scoped accounts and data access, refresh-token rotation, login throttling, audit records, and role controls.
- In-app notifications with an organization-configurable priority threshold; email, webhook, and digest delivery are not implemented.
- Scheduled cleanup for expired, unreferenced snapshots and expired refresh tokens. Current snapshots, snapshots used by findings, reviews, and audit history are retained.

## Data and evaluation limits

The included seed references and frontend mock records are invented examples. They do not represent FDA, WHO, CDC, or other regulator guidance. The small synthetic benchmark is useful only for basic code checks; it does not demonstrate clinical accuracy, safe deployment, or performance on real medical content. A real evaluation needs authorized, current sources and an independently reviewed dataset with enough cases to support meaningful conclusions.

The crawler and analysis workflow do not replace review by qualified professionals. Model-generated output can be incomplete or wrong, and evidence quality depends on the sources configured by each organization.

## Verification record

The project has been revised to address the issues listed in the supplied review PDF. For this revision, Python source compilation and JavaScript syntax checks passed. The frontend production build could not run because its dependencies were available only through the Downloads copy, which the workspace sandbox blocks from reading. Database-backed tests were not run: the fixture drops and recreates its configured database. Docker Compose deployment was also not run.

Before release, run the full suite against a disposable database, verify migrations and scheduled tasks in a local Compose environment, and evaluate with a sufficiently large, independently reviewed dataset.
