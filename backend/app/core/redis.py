from redis.asyncio import Redis, from_url

from app.core.config import settings

_redis: Redis | None = None


def get_redis_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
    return _redis


async def get_redis() -> Redis:
    return get_redis_client()
