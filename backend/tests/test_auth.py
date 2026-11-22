import uuid

import pytest
from sqlalchemy import select

from app.api.v1 import auth as auth_module
from app.core.config import settings
from app.models.config import Config
from app.models.user import User


@pytest.fixture(autouse=True)
async def registration_defaults(db_session, redis_client):
    await db_session.merge(Config(key="registration_open", value="true"))
    await db_session.commit()
    await redis_client.flushdb()


async def csrf(client):
    await client.get("/api/v1/health")
    return client.cookies["csrf_token"]


@pytest.mark.asyncio
async def test_register_login_me_logout(client):
    token = await csrf(client)
    username = f"player_{uuid.uuid4().hex[:8]}"
    payload = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "correct-horse-1",
    }
    registered = await client.post(
        "/api/v1/auth/register", json=payload, headers={"X-CSRF-Token": token}
    )
    assert registered.status_code == 201
    assert "password_hash" not in registered.text
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    assert (
        await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token})
    ).status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_wrong_password_and_csrf_are_rejected(client):
    token = await csrf(client)
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "missing", "password": "correct-horse-1"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 401
    missing_csrf = await client.post(
        "/api/v1/auth/login", json={"username": "missing", "password": "correct-horse-1"}
    )
    assert missing_csrf.status_code == 403


@pytest.mark.asyncio
async def test_registration_closed(client, db_session):
    token = await csrf(client)
    await db_session.merge(Config(key="registration_open", value="false"))
    await db_session.commit()
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "closed_user",
            "email": "closed@example.com",
            "password": "correct-horse-1",
        },
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_banned_user_and_player_admin_protection(client, db_session):
    token = await csrf(client)
    username = f"banned_{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "correct-horse-1",
        },
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201
    user = await db_session.scalar(select(User).where(User.username == username))
    user.is_banned = True
    await db_session.commit()
    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token})
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "correct-horse-1"},
        headers={"X-CSRF-Token": token},
    )
    assert login.status_code == 403


@pytest.mark.asyncio
async def test_player_is_rejected_by_admin_endpoint(client):
    token = await csrf(client)
    username = f"ordinary_{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "correct-horse-1",
        },
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201
    denied = await client.post(
        f"/api/v1/auth/admin/users/{uuid.uuid4()}/reset-token", headers={"X-CSRF-Token": token}
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_login_rate_limit_returns_retry_after(client, monkeypatch):
    token = await csrf(client)
    monkeypatch.setattr(settings, "login_ip_limit", 1)
    monkeypatch.setattr(
        auth_module, "get_client_ip", lambda request: f"198.51.100.{uuid.uuid4().int % 200 + 1}"
    )
    first = await client.post(
        "/api/v1/auth/login",
        json={"username": "unknown-rate", "password": "correct-horse-1"},
        headers={"X-CSRF-Token": token},
    )
    assert first.status_code == 401
    # The patched IP changes per call, so use a stable limiter key for the second request.
    monkeypatch.setattr(auth_module, "get_client_ip", lambda request: "198.51.100.10")
    await client.post(
        "/api/v1/auth/login",
        json={"username": "unknown-rate-2", "password": "correct-horse-1"},
        headers={"X-CSRF-Token": token},
    )
    limited = await client.post(
        "/api/v1/auth/login",
        json={"username": "unknown-rate-3", "password": "correct-horse-1"},
        headers={"X-CSRF-Token": token},
    )
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


@pytest.mark.asyncio
async def test_password_change_revokes_session(client):
    token = await csrf(client)
    username = f"change_{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "correct-horse-1",
        },
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201
    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "correct-horse-1", "new_password": "new-correct-horse-2"},
        headers={"X-CSRF-Token": token},
    )
    assert changed.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401
