# MedGuard AI (medagaurdAI)

MedGuard AI monitors health-related website content and compares extracted claims with a searchable reference library. It is a research/demo tool, not a clinical decision system. The bundled demo corpus is explicitly fictional; it must not be described as FDA guidance. Connect licensed, authoritative sources before using real-world claims.

## Quick start with Docker

Requirements: Docker Desktop with Compose v2, an internet connection, and a Nebius Token Factory API key.

1. Copy `.env.example` to `.env`.
2. Set `POSTGRES_PASSWORD`, `SECRET_KEY`, `SEED_ADMIN_PASSWORD`, and `LLM_API_KEY` in `.env`. Use unique, strong values; keep `.env` private.
3. Start the services:

   ```powershell
   docker compose up --build -d
   docker compose exec api alembic upgrade head
   docker compose exec api python -m scripts.bootstrap
   docker compose exec api python -m scripts.seed_references
   ```

4. Start the frontend in a second terminal:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

Open `http://localhost:5173` and sign in using the `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` values from `.env`. The API is available at `http://localhost:8000`; PostgreSQL and API ports are bound to loopback for local development.

## AI model integration

The default backend uses Nebius Token Factory's OpenAI-compatible Chat Completions API with an NVIDIA Nemotron model. Configure `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` in the environment. The default base URL is `https://api.tokenfactory.us-central1.nebius.com/v1/` and the default model is `nvidia/nemotron-3-super-120b-a12b`. The key is read only from the environment and must never be committed.

For local development, set `LLM_PROVIDER=ollama`, start the optional service with `docker compose --profile local-llm up -d ollama`, and pull a model inside it, for example `docker compose exec ollama ollama pull qwen2.5:1.5b`.

## Reference data and evaluation

`backend/scripts/seed_references.py` loads fictional fixtures for local demonstrations and tests. They are clearly marked as fictional and are not official FDA documents. The benchmark uses a small synthetic dataset; its results are a code-checking aid, not evidence of clinical accuracy or general model performance. Use a larger, independently reviewed dataset before reporting performance metrics.

Run the backend checks from `backend/` after installing `requirements.txt`:

```powershell
pytest
python -m scripts.benchmark
```

The complete API contract and implementation notes are in `backend/docs/`.

## Submission details

- **Demo URL:** Add the deployed demo URL before submitting.
- **Demo video (3 minutes or less):** Add the video link before submitting.
- **Feedback:** Please report bugs, confusing results, and usability suggestions through the project issue tracker or the event submission feedback form.

## Security notes

- Never commit `.env`, backend credentials, database passwords, or API keys.
- Change all local credentials before exposing the application to a network.
- The crawler restricts URLs and ports and is intended for authorized public pages. Review source terms and `robots.txt` before crawling.
- Findings require qualified human review; automated results are not medical advice.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
