from __future__ import annotations

from fastapi import HTTPException, status

from app.utils.redis_client import redis_client


async def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    current = await redis_client.incr(key)
    if current is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Rate limiter unavailable")
    if current == 1:
        await redis_client.expire(key, window_seconds)
    if current > limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
