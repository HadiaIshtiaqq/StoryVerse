import os


class Settings:
    """Runtime configuration, read from environment variables (see .env.example)."""

    def __init__(self) -> None:
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./storyverse.db")
        self.secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
        self.token_ttl_seconds: int = int(os.getenv("TOKEN_TTL_SECONDS", str(7 * 24 * 3600)))
        self.cors_origins: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
        self.environment: str = os.getenv("ENVIRONMENT", "development")


settings = Settings()

if settings.environment != "development" and settings.secret_key == "dev-secret-change-me":
    raise RuntimeError("SECRET_KEY must be set outside development")
