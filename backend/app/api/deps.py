import uuid

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.redis import get_redis
from app.models.user import User
from app.services.lifecycle import (
    get_capabilities,
    get_state,
    parse_datetime,
    read_lifecycle_config,
)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> User:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    value = await redis.get(f"session:{session_id}")
    if not value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user_id = uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=401, detail="Not authenticated") from None
    user = await session.get(User, user_id)
    if user is None or user.is_banned:
        await redis.delete(f"session:{session_id}")
        raise HTTPException(
            status_code=403 if user and user.is_banned else 401, detail="Account unavailable"
        )
    from app.core.config import settings

    await redis.expire(f"session:{session_id}", settings.session_ttl_seconds)
    return user


async def require_user(user: User = Depends(get_current_user)) -> User:
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_capability(name: str):
    async def dependency(
        _user: User = Depends(require_user), session: AsyncSession = Depends(get_session)
    ) -> User:
        values = await read_lifecycle_config(session)
        state = get_state(
            event_start=parse_datetime(values["event_start"]),
            event_end=parse_datetime(values["event_end"]),
            state_override=values["state_override"],
        )
        capabilities = get_capabilities(state)
        if name not in capabilities:
            raise HTTPException(status_code=500, detail=f"Unknown event capability: {name}")
        if not capabilities[name]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Event capability '{name}' is not available while the event is {state}",
            )
        return _user

    return dependency
