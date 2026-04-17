import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import is_db_tls_config_secure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Reproute API", version="0.1.0")

# CORS configuration - origins read from config/env var CORS_ALLOW_ORIGINS (comma-separated)
_settings = get_settings()
cors_origins = [o.strip() for o in _settings.cors_allow_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    response = await call_next(request)
    return _apply_security_headers(response)


@app.on_event("startup")
async def startup():
    logger.info("=== Reproute API starting up ===")
    s = get_settings()
    if s.is_production() and s.poc_mode:
        logger.critical("Refusing startup: POC_MODE must be false in production")
        raise RuntimeError("Invalid startup config: POC_MODE=true in production")
    if s.is_production() and not is_db_tls_config_secure():
        logger.critical("Refusing startup: insecure DB TLS settings")
        raise RuntimeError("Invalid startup config: insecure DB TLS settings")
    if s.is_production():
        if not s.clerk_jwks_url.strip():
            raise RuntimeError("Invalid startup config: CLERK_JWKS_URL is required in production")
        if not s.clerk_jwt_issuer.strip():
            raise RuntimeError("Invalid startup config: CLERK_JWT_ISSUER is required in production")
    logger.info("environment=%s poc_mode=%s", s.environment, s.poc_mode)
    logger.info("database_configured=%s", bool(s.database_url))
    logger.info("redis_configured=%s", bool(s.redis_url))
    logger.info("geocode_worker_url=%s", s.geocode_worker_url)
    logger.info("cors_origins=%s", cors_origins)
    logger.info("=== startup complete ===")


@app.get("/")
async def root():
    return {"status": "ok", "service": "reproute-api"}



@app.head("/")
async def root_head():
    return Response(status_code=200)


app.include_router(api_router)
