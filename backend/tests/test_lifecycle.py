from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.config import Config
from app.models.user import User
from app.services.lifecycle import get_capabilities, get_state

BASE_TIME = datetime(2026, 1, 1, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def lifecycle_defaults(db_session, redis_client):
    await redis_client.flushdb()
    for key, value in {
        "event_start": "",
        "event_end": "",
        "state_override": "none",
        "freeze_enabled": "false",
        "freeze_time": "",
    }.items():
        await db_session.merge(Config(key=key, value=value))
    await db_session.execute(delete(AuditLog))
    await db_session.commit()
    yield
    await db_session.execute(delete(AuditLog))
    for key, value in {
        "event_start": "",
        "event_end": "",
        "state_override": "none",
        "freeze_enabled": "false",
        "freeze_time": "",
    }.items():
        await db_session.merge(Config(key=key, value=value))
    await db_session.commit()


def test_fake_clock_covers_all_four_states():
    assert get_state(BASE_TIME, event_start=BASE_TIME + timedelta(hours=1)) == "draft_upcoming"
    assert get_state(BASE_TIME, event_start=BASE_TIME - timedelta(hours=1)) == "live"
    assert get_state(BASE_TIME, state_override="paused") == "paused"
    assert get_state(BASE_TIME, event_end=BASE_TIME) == "ended"


def test_override_beats_clock_and_capabilities_are_mapped():
    assert (
        get_state(
            BASE_TIME + timedelta(days=2),
            event_start=BASE_TIME - timedelta(days=1),
            event_end=BASE_TIME + timedelta(days=1),
            state_override="paused",
        )
        == "paused"
    )
    assert get_capabilities("live") == {
        "can_view_challenges": True,
        "can_submit": True,
        "can_unlock_hints": True,
        "can_change_roster": False,
        "can_view_scoreboard": True,
    }
    assert get_capabilities("paused")["can_submit"] is False


async def csrf(client):
    await client.get("/api/v1/health")
    return client.cookies["csrf_token"]


async def create_user(db_session, role: str) -> User:
    user = User(
        username=f"{role}_{datetime.now(UTC).timestamp()}".replace(".", ""),
        email=f"{role}_{datetime.now(UTC).timestamp()}@example.com".replace(".", ""),
        password_hash=hash_password("correct-horse-1"),
        role=role,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def login(client, user: User):
    token = await csrf(client)
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "correct-horse-1"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    return token


@pytest.mark.asyncio
async def test_public_status_endpoint_works_without_login(client):
    response = await client.get("/api/v1/event/status")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "draft_upcoming"
    assert set(body["capabilities"]) == {
        "can_view_challenges",
        "can_submit",
        "can_unlock_hints",
        "can_change_roster",
        "can_view_scoreboard",
    }
    assert body["server_time"]
    assert body["start"] is None
    assert body["end"] is None


@pytest.mark.asyncio
async def test_end_before_start_returns_422(client, db_session):
    admin = await create_user(db_session, "admin")
    token = await login(client, admin)
    response = await client.put(
        "/api/v1/event/admin/times",
        json={"start": "2027-01-01T14:00:00Z", "end": "2027-01-01T12:00:00Z"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "Event end must be after event start"


@pytest.mark.asyncio
async def test_lifecycle_admin_endpoints_require_csrf(client, db_session):
    admin = await create_user(db_session, "admin")
    await login(client, admin)
    for method, path in [
        ("put", "/api/v1/event/admin/times"),
        ("post", "/api/v1/event/admin/start"),
        ("post", "/api/v1/event/admin/pause"),
        ("post", "/api/v1/event/admin/resume"),
        ("post", "/api/v1/event/admin/end"),
    ]:
        response = await getattr(client, method)(
            path,
            json={"start": "2027-01-01T12:00:00Z", "end": "2027-01-01T14:00:00Z"}
            if method == "put"
            else None,
        )
        assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_player_is_rejected_by_every_lifecycle_admin_endpoint(client, db_session):
    player = await create_user(db_session, "player")
    token = await login(client, player)
    headers = {"X-CSRF-Token": token}
    endpoints = [
        ("put", "/api/v1/event/admin/times", {"start": None, "end": None}),
        ("post", "/api/v1/event/admin/start", None),
        ("post", "/api/v1/event/admin/pause", None),
        ("post", "/api/v1/event/admin/resume", None),
        ("post", "/api/v1/event/admin/end", None),
    ]
    for method, path, body in endpoints:
        response = await getattr(client, method)(path, json=body, headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"


@pytest.mark.asyncio
async def test_start_after_end_returns_409(client, db_session):
    admin = await create_user(db_session, "admin")
    token = await login(client, admin)
    await client.post("/api/v1/event/admin/end", headers={"X-CSRF-Token": token})
    response = await client.post("/api/v1/event/admin/start", headers={"X-CSRF-Token": token})
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == (
        "Event has already ended; update the event end time before starting it"
    )


@pytest.mark.asyncio
async def test_admin_state_changes_write_audit_rows(client, db_session):
    admin = await create_user(db_session, "admin")
    token = await login(client, admin)

    times = await client.put(
        "/api/v1/event/admin/times",
        json={
            "start": "2027-01-01T12:00:00Z",
            "end": "2027-01-01T14:00:00Z",
        },
        headers={"X-CSRF-Token": token},
    )
    assert times.status_code == 200
    assert times.json()["start"] == "2027-01-01T12:00:00Z"
    assert times.json()["end"] == "2027-01-01T14:00:00Z"

    started = await client.post("/api/v1/event/admin/start", headers={"X-CSRF-Token": token})
    assert started.status_code == 200
    assert started.json()["state"] == "live"
    paused = await client.post("/api/v1/event/admin/pause", headers={"X-CSRF-Token": token})
    assert paused.status_code == 200
    assert paused.json()["state"] == "paused"
    resumed = await client.post("/api/v1/event/admin/resume", headers={"X-CSRF-Token": token})
    assert resumed.status_code == 200
    ended = await client.post("/api/v1/event/admin/end", headers={"X-CSRF-Token": token})
    assert ended.status_code == 200
    assert ended.json()["state"] == "ended"

    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.actor_id == admin.id).order_by(AuditLog.created_at)
        )
    ).all()
    assert [row.action for row in rows] == [
        "event_times_updated",
        "event_started",
        "event_paused",
        "event_resumed",
        "event_ended",
    ]
    assert all(row.actor_id == admin.id for row in rows)
