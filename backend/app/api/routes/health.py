import httpx
from fastapi import APIRouter, Depends, Header
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.utils.redis_client import redis_client

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    db_ok = True
    redis_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    try:
        await redis_client.ping()
    except Exception:
        redis_ok = False

    status = "ok" if (db_ok and redis_ok) else "degraded"
    return {"status": status, "db": "ok" if db_ok else "down", "redis": "ok" if redis_ok else "down"}


@router.get("/debug")
async def debug(authorization: str | None = Header(default=None)) -> dict:
    """Diagnostic endpoint — checks token presence, DB, Redis, and Photon reachability."""
    settings = get_settings()

    # Token
    has_token = authorization is not None and authorization.startswith("Bearer ")
    token_prefix = authorization[:40] + "..." if has_token and authorization else None

    # DB
    db_ok = False
    try:
        from app.db.session import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_err = str(e)
    else:
        db_err = None

    # Redis
    redis_ok = False
    redis_err = None
    try:
        pong = await redis_client.ping()
        redis_ok = pong is not None
    except Exception as e:
        redis_err = str(e)

    # Photon
    photon_ok = False
    photon_err = None
    photon_sample = None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(settings.geocode_worker_url, params={"q": "chicago", "limit": 1})
            photon_ok = resp.status_code == 200
            if photon_ok:
                data = resp.json()
                features = data.get("features", [])
                photon_sample = features[0].get("properties", {}).get("name") if features else "no results"
            else:
                photon_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        photon_err = str(e)

    return {
        "has_token": has_token,
        "token_prefix": token_prefix,
        "clerk_jwks_url": settings.clerk_jwks_url or "NOT SET",
        "clerk_jwt_issuer": settings.clerk_jwt_issuer or "NOT SET",
        "geocode_worker_url": settings.geocode_worker_url,
        "db": "ok" if db_ok else f"down: {db_err}",
        "redis": "ok" if redis_ok else f"down: {redis_err}",
        "photon": "ok" if photon_ok else f"down: {photon_err}",
        "photon_sample": photon_sample,
    }
