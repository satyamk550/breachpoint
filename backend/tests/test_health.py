import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.core.db import get_session
from app.core.redis import get_redis
from app.main import app


@pytest.mark.asyncio
async def test_health_ok(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"]["status"] == "ok"
    assert data["redis"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_returns_503_when_redis_is_unavailable(db_session):
    unavailable_redis = Redis.from_url(
        "redis://127.0.0.1:1/0",
        socket_connect_timeout=0.1,
        retry_on_timeout=False,
    )

    async def override_session():
        yield db_session

    async def override_redis():
        return unavailable_redis

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_redis] = override_redis
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()
        await unavailable_redis.aclose()

    assert response.status_code == 503
    assert response.json()["database"]["status"] == "ok"
    assert response.json()["redis"]["status"] == "error"
