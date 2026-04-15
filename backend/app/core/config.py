from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/reproute"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "dev-secret"

    clerk_jwt_issuer: str = ""
    clerk_jwks_url: str = ""
    clerk_audience: str = ""
    clerk_authorized_party: str = ""

    geocode_worker_url: str = "https://example.workers.dev/geocode"
    geocode_timeout_seconds: int = 4

    ors_api_key: str = ""
    ors_base_url: str = "https://api.openrouteservice.org"
    route_cache_ttl_seconds: int = 86400

    cors_allow_origins: str = "http://localhost:5173"
    poc_mode: bool = False
    poc_user_email: str = "poc@local.dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
