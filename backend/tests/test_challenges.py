import uuid

import pytest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.challenge import Category, Challenge, Flag, Solve, Tag
from app.models.config import Config
from app.models.user import User

PASSWORD = "correct-horse-1"


async def make_user(session: AsyncSession, name: str, role: str = "player") -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"{name}_{suffix}",
        email=f"{name}_{suffix}@example.com",
        password_hash=hash_password(PASSWORD),
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def login(client, user: User) -> None:
    await client.get("/api/v1/health")
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": PASSWORD},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert response.status_code == 200, response.text


async def csrf(client):
    await client.get("/api/v1/health")
    return client.cookies["csrf_token"]


@pytest.fixture(autouse=True)
async def challenge_defaults(db_session, redis_client):
    await redis_client.flushdb()
    await db_session.execute(delete(Solve))
    await db_session.execute(delete(Flag))
    await db_session.execute(delete(Tag))
    await db_session.execute(delete(Challenge))
    await db_session.execute(delete(Category))
    await db_session.execute(update(User).values(team_id=None))
    for key, value in {"event_start": "", "event_end": "", "state_override": "live"}.items():
        await db_session.merge(Config(key=key, value=value))
    await db_session.commit()
    yield


async def setup(client, db_session):
    admin = await make_user(db_session, "admin", "admin")
    player = await make_user(db_session, "player")
    await login(client, admin)
    player_client = type(client)(transport=client._transport, base_url="https://test")
    await login(player_client, player)
    category = Category(name=f"web-{uuid.uuid4().hex[:6]}", sort_order=1)
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return admin, player, player_client, category


async def create_challenge(client, category_id, title="Visible", visibility="visible", **extra):
    payload = {
        "title": title,
        "description_md": "Description",
        "category_id": str(category_id),
        "points": 100,
        "scoring_mode": "static",
        "initial": 100,
        "minimum": 0,
        "decay": 1,
        "function": "linear",
        "visibility": visibility,
        "tags": ["web"],
        "prerequisites": [],
    }
    payload.update(extra)
    response = await client.post(
        "/api/v1/admin/challenges",
        json=payload,
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_player_eligibility_states_and_no_team(client, db_session):
    admin, player, player_client, category = await setup(client, db_session)
    await create_challenge(client, category.id)
    hidden = await create_challenge(client, category.id, "Hidden", "hidden")
    draft = await create_challenge(client, category.id, "Draft", "draft")
    assert (await player_client.get("/api/v1/challenges")).status_code == 403
    from app.models.team import Team

    team = Team(
        name=f"T-{uuid.uuid4().hex[:8]}",
        join_secret_hash=hash_password(PASSWORD),
        captain_id=player.id,
    )
    db_session.add(team)
    await db_session.flush()
    player.team_id = team.id
    await db_session.commit()
    listing = await player_client.get("/api/v1/challenges")
    assert (
        listing.status_code == 200
        and "Visible" in listing.text
        and "Hidden" not in listing.text
        and "Draft" not in listing.text
    )
    assert (await player_client.get(f"/api/v1/challenges/{hidden['id']}")).status_code == 404
    assert (await player_client.get(f"/api/v1/challenges/{draft['id']}")).status_code == 404
    await player_client.aclose()


@pytest.mark.asyncio
async def test_prerequisite_unlock_and_cycle_rejection(client, db_session):
    _, player, player_client, category = await setup(client, db_session)
    first = await create_challenge(client, category.id, "First")
    locked = await create_challenge(client, category.id, "Locked", prerequisites=[first["id"]])
    from app.models.team import Team

    team = Team(
        name=f"T-{uuid.uuid4().hex[:8]}",
        join_secret_hash=hash_password(PASSWORD),
        captain_id=player.id,
    )
    db_session.add(team)
    await db_session.flush()
    player.team_id = team.id
    await db_session.commit()
    assert (await player_client.get(f"/api/v1/challenges/{locked['id']}")).status_code == 404
    db_session.add(Solve(team_id=team.id, challenge_id=uuid.UUID(first["id"]), user_id=player.id))
    await db_session.commit()
    assert (await player_client.get(f"/api/v1/challenges/{locked['id']}")).status_code == 200
    cycle = await create_challenge(client, category.id, "Cycle")
    response = await client.patch(
        f"/api/v1/admin/challenges/{cycle['id']}",
        json={"prerequisites": [locked["id"]]},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert response.status_code == 200
    response = await client.patch(
        f"/api/v1/admin/challenges/{locked['id']}",
        json={"prerequisites": [cycle["id"]]},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert response.status_code == 422
    await player_client.aclose()


@pytest.mark.asyncio
async def test_admin_crud_clone_bulk_delete_and_flag_secrecy(client, db_session):
    admin, player, player_client, category = await setup(client, db_session)
    item = await create_challenge(client, category.id, connection_info="tcp://example")
    secret = "FLAG-DO-NOT-LEAK"
    response = await client.post(
        f"/api/v1/admin/challenges/{item['id']}/flags",
        json={"type": "static", "content": secret},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert response.status_code == 201
    assert secret not in (await client.get("/api/v1/admin/challenges")).text
    assert secret not in (await client.get(f"/api/v1/admin/challenges/{item['id']}")).text
    assert secret not in (await player_client.get("/api/v1/challenges")).text
    clone = await client.post(
        f"/api/v1/admin/challenges/{item['id']}/clone",
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert (
        clone.status_code == 201
        and clone.json()["title"].endswith("(copy)")
        and clone.json()["visibility"] == "draft"
    )
    bulk = await client.post(
        "/api/v1/admin/challenges/visibility",
        json={"visibility": "hidden", "challenge_ids": [item["id"]]},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert bulk.status_code == 200
    assert (
        await client.delete(
            f"/api/v1/admin/categories/{category.id}",
            headers={"X-CSRF-Token": client.cookies["csrf_token"]},
        )
    ).status_code == 409
    await player_client.aclose()


@pytest.mark.asyncio
async def test_validation_audit_and_admin_authorization(client, db_session):
    admin, player, player_client, category = await setup(client, db_session)
    bad = await client.post(
        "/api/v1/admin/challenges",
        json={"title": "x", "description_md": "x", "category_id": str(category.id), "points": -1},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert bad.status_code == 422
    bad = await client.post(
        "/api/v1/admin/challenges",
        json={
            "title": "x",
            "description_md": "x",
            "category_id": str(category.id),
            "scoring_mode": "dynamic",
            "initial": 1,
            "minimum": 2,
        },
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert bad.status_code == 422
    item = await create_challenge(client, category.id)
    bad = await client.post(
        f"/api/v1/admin/challenges/{item['id']}/flags",
        json={"type": "regex", "content": "["},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert bad.status_code == 422
    paths = [
        "/api/v1/admin/categories",
        "/api/v1/admin/challenges",
        f"/api/v1/admin/challenges/{item['id']}",
        f"/api/v1/admin/challenges/{item['id']}/flags",
    ]
    for path in paths:
        assert (await player_client.get(path)).status_code == 403
    from sqlalchemy import select

    rows = (
        await db_session.scalars(
            select(__import__("app.models.audit_log", fromlist=["AuditLog"]).AuditLog)
        )
    ).all()
    assert rows and all("FLAG" not in str(row.meta) for row in rows)
    await player_client.aclose()
