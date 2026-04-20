import logging
import time
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import is_db_tls_config_secure
from app.utils.http_clients import close_http_clients, init_http_clients

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _validate_startup_config() -> None:
    import re as _re

    logger.info("=== Reproute API starting up ===")
    s = get_settings()
    if s.is_production() and s.poc_mode:
        logger.critical("Refusing startup: POC_MODE must be false in production")
        raise RuntimeError("Invalid startup config: POC_MODE=true in production")
    if s.is_production() and not is_db_tls_config_secure():
        if (
            s.database_tls_emergency_insecure_override
            and date.today() <= s.database_tls_emergency_override_sunset
        ):
            logger.critical(
                "Emergency DB TLS override active until %s; startup allowed with insecure DB TLS",
                s.database_tls_emergency_override_sunset.isoformat(),
            )
        else:
            logger.critical("Refusing startup: insecure DB TLS settings in production")
            raise RuntimeError("Invalid startup config: insecure DB TLS settings")
    if s.is_production():
        if not s.clerk_jwks_url.strip():
            raise RuntimeError("Invalid startup config: CLERK_JWKS_URL is required in production")
        if not s.clerk_jwt_issuer.strip():
            raise RuntimeError("Invalid startup config: CLERK_JWT_ISSUER is required in production")
        if not s.validation_hmac_secret.strip():
            raise RuntimeError("Invalid startup config: VALIDATION_HMAC_SECRET is required in production")
    if cors_origin_regex:
        try:
            _re.compile(cors_origin_regex)
        except _re.error as exc:
            raise RuntimeError(f"Invalid startup config: CORS_ALLOW_ORIGIN_REGEX is not a valid regex: {exc}") from exc
    logger.info("environment=%s poc_mode=%s", s.environment, s.poc_mode)
    logger.info("database_configured=%s", bool(s.database_url))
    logger.info("redis_configured=%s", bool(s.redis_url))
    logger.info("geocode_worker_url=%s", s.geocode_worker_url)
    logger.info("cors_origins=%s", cors_origins)
    logger.info("cors_origin_regex=%s", cors_origin_regex)
    logger.info("=== startup complete ===")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _validate_startup_config()
    await init_http_clients()
    try:
        yield
    finally:
        await close_http_clients()


app = FastAPI(title="Reproute API", version="0.1.0", lifespan=lifespan)


async def startup() -> None:
    # Backward-compatible startup hook used by tests/imports.
    _validate_startup_config()

# CORS configuration - origins read from config/env var CORS_ALLOW_ORIGINS (comma-separated)
_settings = get_settings()
cors_origins = [o.strip() for o in _settings.cors_allow_origins.split(",") if o.strip()]
cors_origin_regex = _settings.cors_allow_origin_regex.strip() or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)


def _should_emit_audit_log(method: str, path: str, status_code: int) -> bool:
    if path.startswith("/health"):
        return False
    if path.startswith("/admin"):
        return True
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return True
    if status_code in {401, 403, 429}:
        return True
    return False

def _apply_security_headers(response: Response) -> Response:
    settings = get_settings()
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if settings.is_production():
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.middleware("http")
async def request_size_and_security_headers(request: Request, call_next):
    settings = get_settings()
    content_length_raw = request.headers.get("content-length")
    if content_length_raw:
        try:
            content_length = int(content_length_raw)
        except ValueError:
            response = JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
            return _apply_security_headers(response)
        if content_length > settings.request_body_limit_bytes:
            response = JSONResponse(status_code=413, content={"detail": "Request body too large"})
            return _apply_security_headers(response)
    t_start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - t_start) * 1000)
    response = _apply_security_headers(response)
    if _should_emit_audit_log(request.method, request.url.path, response.status_code):
        client_host = request.client.host if request.client else "unknown"
        logger.info(
            "audit_event method=%s path=%s status=%s duration_ms=%d client=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_host,
        )
    return response


@app.get("/")
async def root():
    return {"status": "ok", "service": "reproute-api"}



@app.head("/")
async def root_head():
    return Response(status_code=200)


app.include_router(api_router)
