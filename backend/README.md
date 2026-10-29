# MedGuard AI Backend

MedGuard AI is a research and demonstration system that monitors approved websites and compares extracted medical claims with documents loaded into an organization's reference library. It flags potential discrepancies for qualified human review; it is not a clinical decision system.

## Stack

- **Operating systems:** Windows 10/11, Linux, or macOS
- **Language and API:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic
- **Database:** PostgreSQL with the `pgvector` extension
- **Background work:** Redis, Celery, and Celery Beat
- **AI workflow:** LangGraph; Nebius Token Factory by default (OpenAI-compatible API), with Ollama as a local option
- **Embeddings and retrieval:** FastEmbed (`BAAI/bge-small-en-v1.5`), pgvector, and PostgreSQL text search
- **Crawling:** HTTPX, Trafilatura, BeautifulSoup; Playwright is optional

The database vector column is fixed at 384 dimensions. Changing the embedding model requires confirming its output dimension and adding a migration to rebuild stored vectors.

## Local setup

1. Install Python 3.12+, PostgreSQL with pgvector, and Redis.
2. From this directory, create a virtual environment and install dependencies:

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and configure a strong `SECRET_KEY`, database and Redis URLs, an admin password, and the model provider credentials. Do not commit `.env`.
4. Initialize the database and the demo organization:

   ```powershell
   alembic upgrade head
   python -m scripts.bootstrap
   python -m scripts.seed_references
   ```

   The bundled reference records are invented fixtures. They are not official regulatory guidance and must not be used for medical decisions.
5. Run the API and worker in separate terminals:

   ```powershell
   uvicorn app.main:app --reload --port 8000
   celery -A app.workers.celery_app.celery_app worker --loglevel=info
   celery -A app.workers.celery_app.celery_app beat --loglevel=info
   ```

The API documentation is available at `http://localhost:8000/docs`.

## Model configuration

Set `LLM_PROVIDER=nebius` and provide `LLM_API_KEY` for Nebius Token Factory. The default model is `nvidia/nemotron-3-super-120b-a12b`. For local inference, set `LLM_PROVIDER=ollama`, configure `OLLAMA_BASE_URL`, and pull the selected model first. Model output is treated as untrusted and checked against retrieved source text.

## Accounts and registration

`POST /api/v1/auth/register` creates a new workspace and makes its first registrant an administrator. The new account is signed in immediately. Email ownership verification is not implemented, so public deployments should add verification or restrict access to the registration route before accepting real users. Administrators can add additional workspace members from the Administration page.

## Operations and limitations

- Run `alembic upgrade head` after updating the application.
- Celery Beat schedules monitoring, stuck-job recovery, and cleanup of expired, unreferenced snapshots and refresh tokens. Current page versions, findings, reviews, and audit history are retained.
- The notification preference controls in-app notification priority. Email, webhook, and digest delivery are not implemented and are not presented as available settings.
- Load authorized and current reference documents before evaluating real claims. Demo fixtures and the small synthetic benchmark do not establish clinical accuracy.
- Crawler access is constrained by robots rules, rate limits, allowed ports, and SSRF checks. `ALLOW_LOCAL_TARGETS` is only for local development and must remain disabled in production.
- Findings are for human review only. They do not provide medical advice or change monitored websites.

## Checks

Run the test suite from this directory with `pytest app/tests -q`. Tests that need PostgreSQL or Redis require those services to be configured and running. See `docs/` for the API contract, risk scoring notes, and benchmark limits.
