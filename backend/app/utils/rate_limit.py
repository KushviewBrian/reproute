from __future__ import annotations

from fastapi import HTTPException, status

from app.utils.redis_client import redis_client


async def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    current = await redis_client.incr(key)
    # Fail open for POC/reliability: if Redis is unavailable, do not block core app flows.
    if current is None:
        return
    if current == 1:
        await redis_client.expire(key, window_seconds)
    if current > limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
