import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import get_session
from app.core.redis import get_redis
from app.main import app


@pytest.fixture
async def engine():
    eng = create_async_engine(settings.database_url, echo=False)
    async with eng.connect() as connection:
        await connection.exec_driver_sql("SELECT 1")
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def redis_client():
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def client(db_session, redis_client):
    async def override_session():
        yield db_session

    async def override_redis():
        return redis_client

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_redis] = override_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as ac:
        yield ac

    app.dependency_overrides.clear()
