from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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

    if db_ok and redis_ok:
        return {"status": "ok", "db": "ok", "redis": "ok"}
    return {"status": "degraded", "db": "ok" if db_ok else "down", "redis": "ok" if redis_ok else "down"}
