from __future__ import annotations

import logging

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.utils.redis_client import redis_client

logger = logging.getLogger(__name__)


async def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    current = await redis_client.incr(key)
    if current is None:
        # Redis unavailable: fail open, but log a critical warning in production so
        # ops teams know rate limiting is not enforced.
        if get_settings().is_production():
            logger.critical("rate_limit_redis_unavailable key=%s — rate limiting bypassed in production", key)
        return
    if current == 1:
        await redis_client.expire(key, window_seconds)
    if current > limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
