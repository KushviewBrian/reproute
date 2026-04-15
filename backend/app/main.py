import logging

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

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


@app.on_event("startup")
async def startup():
    logger.info("=== Reproute API starting up ===")
    s = get_settings()
    logger.info("environment=%s poc_mode=%s", s.environment, s.poc_mode)
    logger.info("database_url=%s", s.database_url[:40] + "..." if len(s.database_url) > 40 else s.database_url)
    logger.info("redis_url=%s", s.redis_url[:40] + "..." if len(s.redis_url) > 40 else s.redis_url)
    logger.info("geocode_worker_url=%s", s.geocode_worker_url)
    logger.info("cors_origins=%s", cors_origins)
    logger.info("=== startup complete ===")


@app.get("/")
async def root():
    return {"status": "ok", "service": "reproute-api"}


@app.get("/dbcheck")
async def dbcheck():
    from sqlalchemy import text
    from app.db.session import get_db
    from app.core.config import get_settings
    s = get_settings()
    try:
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            return {"db": "ok", "ssl": "require" in str(s.database_url) or True}
    except Exception as e:
        return {"db": "down", "error": str(e), "url_prefix": s.database_url[:60]}


@app.head("/")
async def root_head():
    return Response(status_code=200)


app.include_router(api_router)
