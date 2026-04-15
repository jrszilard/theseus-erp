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

    @property
    def database_url_sync(self) -> str:
        """Sync URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "")


settings = Settings()
