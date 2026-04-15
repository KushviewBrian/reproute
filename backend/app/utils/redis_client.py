from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()
_raw_client = Redis.from_url(settings.redis_url, decode_responses=True)


class SafeRedisClient:
    async def get(self, key: str):
        try:
            return await _raw_client.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ex: int | None = None):
        try:
            return await _raw_client.set(key, value, ex=ex)
        except Exception:
            return True

    async def incr(self, key: str):
        try:
            return await _raw_client.incr(key)
        except Exception:
            return 1

    async def expire(self, key: str, seconds: int):
        try:
            return await _raw_client.expire(key, seconds)
        except Exception:
            return True

    async def ping(self):
        try:
            return await _raw_client.ping()
        except Exception:
            return "NOOP"


redis_client = SafeRedisClient()
