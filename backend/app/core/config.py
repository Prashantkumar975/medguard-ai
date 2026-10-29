"""Application configuration (environment-driven, no secrets in code)."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- core ---
    app_name: str = "MedGuard AI"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    # Must be explicitly configured; startup validation rejects the placeholder.
    secret_key: str = ""
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- datastores ---
    database_url: str = "postgresql+psycopg://medguard:medguard@127.0.0.1:5432/medguard"
    test_database_url: str = "postgresql+psycopg://medguard:medguard@127.0.0.1:5432/medguard_test"
    redis_url: str = "redis://127.0.0.1:6379/0"

    # --- auth ---
    login_rate_limit_enabled: bool = True
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_s: int = 60

    # --- crawling ---
    crawl_user_agent: str = "MedGuardAI/0.1"
    crawl_max_pages_per_scan: int = 25
    crawl_concurrency: int = 4
    crawl_delay_ms: int = 250
    robots_cache_ttl_s: int = 3600
    fetch_timeout_s: float = 20.0
    fetch_max_bytes: int = 5_000_000
    fetch_max_redirects: int = 5
    allowed_ports: str = "80,443,8000,8080,8443,5173,8090"
    # Dev/demo only: permit loopback targets (local demo site). Never enable in production.
    allow_local_targets: bool = False
    js_render_enabled: bool = False  # Playwright fallback; requires `playwright install chromium`
    js_render_timeout_s: float = 30.0
    snapshot_dir: str = "data/snapshots"

    # --- LLM (Nebius Token Factory by default; Ollama remains available locally) ---
    llm_provider: str = "nebius"
    llm_base_url: str = "https://api.tokenfactory.us-central1.nebius.com/v1/"
    llm_api_key: str = ""
    llm_model: str = "nvidia/nemotron-3-super-120b-a12b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:1.5b"
    llm_timeout_s: float = 180.0
    llm_max_retries: int = 2

    # --- embeddings / retrieval ---
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Database migrations fix the vector column at 384 dimensions. Change this
    # only together with a new migration and a full embedding rebuild.
    retrieval_top_k: int = 5
    retrieval_pool_k: int = 20
    retrieval_min_similarity: float = 0.35

    # --- workers ---
    task_always_eager: bool = False  # tests / no-worker dev mode
    scan_default_max_pages: int = 25
    # Beat reaper: pending scans/rechecks older than this are failed/reverted.
    # Must exceed the worst-case task runtime (task_time_limit=40min x 3 attempts).
    reaper_stale_minutes: int = 180

    # --- demo bootstrap ---
    seed_admin_email: str = "admin@medguard.local"
    seed_admin_password: str = ""
    seed_admin_name: str = "MedGuard Admin"
    seed_org_name: str = "MedGuard Demo Org"

    @model_validator(mode="after")
    def validate_security_configuration(self):
        if self.environment == "test" and not self.secret_key:
            self.secret_key = "test-only-secret-key-not-for-deployment-00000000"
        elif len(self.secret_key.encode("utf-8")) < 32:
            raise ValueError("SECRET_KEY must be set to at least 32 bytes")
        if self.llm_provider.lower() not in {"nebius", "openai_compatible", "ollama"}:
            raise ValueError("LLM_PROVIDER must be nebius, openai_compatible, or ollama")
        return self

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
