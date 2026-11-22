from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings
from app.core.security import new_token


async def create_session(redis: Redis, user_id: UUID) -> str:
    session_id = new_token()
    await redis.setex(f"session:{session_id}", settings.session_ttl_seconds, str(user_id))
    await redis.sadd(f"user_sessions:{user_id}", session_id)
    return session_id


async def delete_session(redis: Redis, session_id: str | None) -> None:
    if session_id:
        await redis.delete(f"session:{session_id}")


async def delete_all_sessions(redis: Redis, user_id: UUID) -> None:
    key = f"user_sessions:{user_id}"
    sessions = await redis.smembers(key)
    if sessions:
        await redis.delete(*(f"session:{item}" for item in sessions))
    await redis.delete(key)
