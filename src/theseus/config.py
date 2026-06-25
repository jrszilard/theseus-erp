from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://theseus:theseus@localhost:5432/theseus"

    # Auth
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 480

    # LLM (all optional — system works without AI)
    llm_provider: str = ""
    llm_model: str = ""
    llm_api_key: str = ""

    # App
    log_level: str = "INFO"
    debug: bool = False
    enforce_production: bool = False
    # Uploads (browser-facing). The Caddy request-body cap is the hard backstop.
    max_upload_bytes: int = 25 * 1024 * 1024

    # Object storage (DAM)
    storage_backend: str = "minio"  # "minio" | "s3" | "local"
    storage_endpoint: str = "http://localhost:9000"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"
    storage_bucket: str = "theseus-assets"
    storage_region: str = "us-east-1"
    storage_presign_ttl_seconds: int = 3600
    storage_local_root: str = "./_asset_store"

    @property
    def database_url_sync(self) -> str:
        """Sync URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "")


settings = Settings()
