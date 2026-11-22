from fastapi import APIRouter, Depends, Response
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.redis import get_redis
from app.schemas.health import HealthResponse, ServiceStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> HealthResponse:
    db_status: ServiceStatus
    try:
        await session.execute(text("SELECT 1"))
        db_status = ServiceStatus(status="ok")
    except SQLAlchemyError:
        db_status = ServiceStatus(status="error", detail="unavailable")

    redis_status: ServiceStatus
    try:
        await redis.ping()
        redis_status = ServiceStatus(status="ok")
    except RedisError:
        redis_status = ServiceStatus(status="error", detail="unavailable")

    overall = "ok" if db_status.status == "ok" and redis_status.status == "ok" else "degraded"
    if overall != "ok":
        response.status_code = 503

    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
    )
