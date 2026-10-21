"""Application configuration (environment-driven, no secrets in code)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- core ---
    app_name: str = "MedGuard AI"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    # NOTE: keep >= 32 bytes for HS256 (RFC 7518). The default is for local dev
    # only — override via SECRET_KEY in .env for anything shared or deployed.
    secret_key: str = "dev-only-change-me-set-a-longer-secret-key-please-32b"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- datastores ---
    database_url: str = "postgresql+psycopg://postgres@127.0.0.1:5433/medguard"
    test_database_url: str = "postgresql+psycopg://postgres@127.0.0.1:5433/medguard_test"
    redis_url: str = "redis://127.0.0.1:6379/0"

    # --- auth ---
    login_rate_limit_enabled: bool = True
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_s: int = 60

    # --- crawling ---
    crawl_user_agent: str = (
        "MedGuardAI/0.1 (+https://github.com/Prashantkumar975/medguard-ai; healthcare content monitoring)"
    )
    crawl_max_pages_per_scan: int = 25
    crawl_concurrency: int = 4
    crawl_delay_ms: int = 250
    fetch_timeout_s: float = 20.0
    fetch_max_bytes: int = 5_000_000
    fetch_max_redirects: int = 5
    allowed_ports: str = "80,443,8000,8080,8443,5173,8090"
    # Dev/demo only: permit loopback targets (local demo site). Never enable in production.
    allow_local_targets: bool = False
    js_render_enabled: bool = False  # Playwright fallback; requires `playwright install chromium`
    js_render_timeout_s: float = 30.0
    snapshot_dir: str = "data/snapshots"

    # --- LLM (Ollama for local dev; any OpenAI-compatible server via URL for vLLM) ---
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:1.5b"
    llm_timeout_s: float = 180.0
    llm_max_retries: int = 2

    # --- embeddings / retrieval ---
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    retrieval_top_k: int = 5
    retrieval_pool_k: int = 20

    # --- workers ---
    task_always_eager: bool = False  # tests / no-worker dev mode
    scan_default_max_pages: int = 25
    # Beat reaper: pending scans/rechecks older than this are failed/reverted.
    # Must exceed the worst-case task runtime (task_time_limit=40min x 3 attempts).
    reaper_stale_minutes: int = 180

    # --- demo bootstrap ---
    seed_admin_email: str = "admin@medguard.local"
    seed_admin_password: str = "ChangeMe123!"
    seed_admin_name: str = "MedGuard Admin"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_port_set(self) -> set[int]:
        return {int(p) for p in allowed_ports_csv(self.allowed_ports)}


def allowed_ports_csv(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
