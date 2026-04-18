from functools import lru_cache
from datetime import date
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/reproute"
    database_ssl_ca_pem: str = ""
    database_tls_verify: bool = False
    database_tls_emergency_insecure_override: bool = False
    database_tls_emergency_override_sunset: date = date(2026, 6, 30)
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "dev-secret"

    clerk_jwt_issuer: str = ""
    clerk_jwks_url: str = ""
    clerk_audience: str = ""
    clerk_authorized_party: str = ""

    geocode_worker_url: str = "https://photon.komoot.io/api/"
    geocode_timeout_seconds: int = 4

    ors_api_key: str = ""
    ors_base_url: str = "https://api.openrouteservice.org"
    route_cache_ttl_seconds: int = 86400
    ingest_database_url: str = ""
    admin_import_secret: str = ""
    admin_allowed_emails: str = ""
    admin_import_allowed_roots: str = ""
    validation_hmac_secret: str = ""
    validation_daily_cap: int = 50
    validation_monthly_cap: int = 2000
    validation_per_user_daily_cap: int = 15
    validation_http_timeout_seconds: int = 5
    validation_retry_delay_seconds: int = 3
    validation_admin_token_ttl_seconds: int = 60

    cors_allow_origins: str = "http://localhost:5173"
    cors_allow_origin_regex: str = ""
    request_body_limit_bytes: int = 1_048_576
    poc_mode: bool = False
    poc_user_email: str = "poc@local.dev"

    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    def should_verify_jwt_signature(self) -> bool:
        return self.environment.strip().lower() not in {"development", "test"}

    def admin_allowed_email_set(self) -> set[str]:
        raw = [value.strip().lower() for value in self.admin_allowed_emails.split(",")]
        return {value for value in raw if value}

    def admin_import_allowed_root_paths(self) -> list[Path]:
        raw = [value.strip() for value in self.admin_import_allowed_roots.split(",")]
        paths: list[Path] = []
        for value in raw:
            if not value:
                continue
            paths.append(Path(value).expanduser().resolve())
        return paths


@lru_cache
def get_settings() -> Settings:
    return Settings()
