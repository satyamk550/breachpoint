# ruff: noqa: E501

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.api.v1.teams as teams_api
from app.api.deps import get_redis, get_session
from app.core.config import settings
from app.core.security import hash_password
from app.main import app
from app.models.config import Config
from app.models.team import Team
from app.models.user import User

PASSWORD = "correct-horse-1"


@pytest.fixture(autouse=True)
async def team_defaults(db_session, redis_client):
    await redis_client.flushdb()
    await db_session.execute(update(User).values(team_id=None))
    await db_session.execute(delete(Team))
    for key, value in {
        "event_start": "",
        "event_end": "",
        "state_override": "none",
        "team_size": "4",
        "max_teams": "25",
    }.items():
        await db_session.merge(Config(key=key, value=value))
    await db_session.commit()
    yield
    await db_session.execute(update(User).values(team_id=None))
    await db_session.execute(delete(Team))
    await db_session.commit()


async def make_user(db_session: AsyncSession, prefix: str = "player") -> User:
    suffix = uuid.uuid4().hex[:10]
    user = User(
        username=f"{prefix}_{suffix}",
        email=f"{prefix}_{suffix}@example.com",
        password_hash=hash_password(PASSWORD),
        role="player",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def csrf(client: AsyncClient) -> str:
    await client.get("/api/v1/health")
    return client.cookies["csrf_token"]


async def login(client: AsyncClient, user: User) -> None:
    token = await csrf(client)
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": PASSWORD},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200, response.text


async def new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://test")


async def make_isolated_clients(count: int, redis_client) -> list[AsyncClient]:
    isolated_engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(isolated_engine, expire_on_commit=False)

    async def isolated_session():
        async with session_factory() as session:
            yield session

    async def isolated_redis():
        return redis_client

    app.dependency_overrides[get_session] = isolated_session
    app.dependency_overrides[get_redis] = isolated_redis
    app.state.team_test_engine = isolated_engine
    return [await new_client() for _ in range(count)]


async def create_team(client: AsyncClient, name: str) -> dict:
    token = await csrf(client)
    response = await client.post(
        "/api/v1/teams",
        json={"name": name},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_join_and_secret_never_leaks(client, db_session):
    captain = await make_user(db_session, "captain")
    await login(client, captain)
    created = await create_team(client, "Alpha")
    assert created["join_secret"]
    assert "join_secret_hash" not in str(created)

    me = await client.get("/api/v1/teams/me")
    profile = await client.get("/api/v1/auth/me")
    public = await client.get("/api/v1/teams")
    detail = await client.get(f"/api/v1/teams/{created['team']['id']}")
    assert all("join_secret" not in response.text and "join_secret_hash" not in response.text for response in (me, profile, public, detail))

    member = await make_user(db_session, "member")
    member_client = await new_client()
    await login(member_client, member)
    token = member_client.cookies["csrf_token"]
    joined = await member_client.post(
        "/api/v1/teams/join",
        json={"name": "alpha", "secret": created["join_secret"]},
        headers={"X-CSRF-Token": token},
    )
    assert joined.status_code == 200
    assert "join_secret" not in joined.text and "join_secret_hash" not in joined.text
    await member_client.aclose()


@pytest.mark.asyncio
async def test_wrong_secret_is_generic_and_rate_limited(client, db_session, monkeypatch):
    captain = await make_user(db_session, "captain")
    await login(client, captain)
    await create_team(client, "Secret Team")
    member = await make_user(db_session, "member")
    member_client = await new_client()
    await login(member_client, member)
    monkeypatch.setattr(settings, "join_user_limit", 1)
    token = member_client.cookies["csrf_token"]
    first = await member_client.post("/api/v1/teams/join", json={"name": "unknown", "secret": "wrong"}, headers={"X-CSRF-Token": token})
    second = await member_client.post("/api/v1/teams/join", json={"name": "secret team", "secret": "wrong"}, headers={"X-CSRF-Token": token})
    assert first.status_code == 401
    assert first.json()["detail"] == "Invalid team name or join secret"
    assert second.status_code == 429
    assert "Retry-After" in second.headers
    await member_client.aclose()


@pytest.mark.asyncio
async def test_unknown_team_and_wrong_secret_share_generic_error(client, db_session):
    captain = await make_user(db_session, "captain")
    member = await make_user(db_session, "member")
    await login(client, captain)
    await create_team(client, "Known Team")
    member_client = await new_client()
    await login(member_client, member)
    token = member_client.cookies["csrf_token"]
    unknown = await member_client.post(
        "/api/v1/teams/join",
        json={"name": "No Such Team", "secret": "wrong-secret"},
        headers={"X-CSRF-Token": token},
    )
    wrong = await member_client.post(
        "/api/v1/teams/join",
        json={"name": "Known Team", "secret": "wrong-secret"},
        headers={"X-CSRF-Token": token},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"] == "Invalid team name or join secret"
    await member_client.aclose()


@pytest.mark.asyncio
async def test_captain_actions_leave_rules_and_member_protection(client, db_session):
    captain = await make_user(db_session, "captain")
    member = await make_user(db_session, "member")
    await login(client, captain)
    created = await create_team(client, "Roster")
    member_client = await new_client()
    await login(member_client, member)
    token = member_client.cookies["csrf_token"]
    await member_client.post("/api/v1/teams/join", json={"name": "Roster", "secret": created["join_secret"]}, headers={"X-CSRF-Token": token})
    captain_team = await client.get("/api/v1/teams/me")
    kick = await member_client.post(f"/api/v1/teams/{created['team']['id']}/kick", json={"user_id": str(captain.id)}, headers={"X-CSRF-Token": token})
    assert kick.status_code == 403
    rename = await member_client.patch(f"/api/v1/teams/{created['team']['id']}/rename", json={"name": "Not Allowed"}, headers={"X-CSRF-Token": token})
    rotate = await member_client.post(f"/api/v1/teams/{created['team']['id']}/rotate-secret", headers={"X-CSRF-Token": token})
    transfer = await member_client.post(f"/api/v1/teams/{created['team']['id']}/transfer-captain", json={"user_id": str(captain.id)}, headers={"X-CSRF-Token": token})
    assert rename.status_code == rotate.status_code == transfer.status_code == 403
    leave = await client.post("/api/v1/teams/leave", headers={"X-CSRF-Token": client.cookies["csrf_token"]})
    assert leave.status_code == 409
    assert captain_team.status_code == 200
    await member_client.aclose()


@pytest.mark.asyncio
async def test_last_member_leaving_deletes_team(client, db_session):
    captain = await make_user(db_session, "captain")
    await login(client, captain)
    created = await create_team(client, "Temporary")
    left = await client.post("/api/v1/teams/leave", headers={"X-CSRF-Token": client.cookies["csrf_token"]})
    assert left.status_code == 204
    assert (await client.get(f"/api/v1/teams/{created['team']['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_hidden_and_banned_teams_are_excluded_and_inaccessible(client, db_session):
    hidden = Team(name="Hidden Team", join_secret_hash=hash_password(PASSWORD), is_hidden=True)
    banned = Team(name="Banned Team", join_secret_hash=hash_password(PASSWORD), is_banned=True)
    db_session.add_all([hidden, banned])
    await db_session.commit()
    public = await client.get("/api/v1/teams")
    assert {team["name"] for team in public.json()} == set()
    assert (await client.get(f"/api/v1/teams/{hidden.id}")).status_code == 404
    assert (await client.get(f"/api/v1/teams/{banned.id}")).status_code == 404


@pytest.mark.asyncio
async def test_teams_with_one_to_three_members_are_valid(client, db_session):
    captain = await make_user(db_session, "captain")
    members = [await make_user(db_session, "member") for _ in range(2)]
    await login(client, captain)
    created = await create_team(client, "Small Team")
    for member in members:
        member_client = await new_client()
        await login(member_client, member)
        joined = await member_client.post(
            "/api/v1/teams/join",
            json={"name": "Small Team", "secret": created["join_secret"]},
            headers={"X-CSRF-Token": member_client.cookies["csrf_token"]},
        )
        assert joined.status_code == 200
        await member_client.aclose()
    detail = await client.get(f"/api/v1/teams/{created['team']['id']}")
    assert detail.status_code == 200
    assert detail.json()["member_count"] == 3


@pytest.mark.asyncio
async def test_roster_locks_when_live_and_admin_can_replace(client, db_session):
    captain = await make_user(db_session, "captain")
    outgoing = await make_user(db_session, "outgoing")
    incoming = await make_user(db_session, "incoming")
    admin = await make_user(db_session, "admin")
    admin.role = "admin"
    await db_session.commit()
    await login(client, captain)
    created = await create_team(client, "Locked")
    member_client = await new_client()
    await login(member_client, outgoing)
    token = member_client.cookies["csrf_token"]
    await member_client.post("/api/v1/teams/join", json={"name": "Locked", "secret": created["join_secret"]}, headers={"X-CSRF-Token": token})
    await db_session.merge(Config(key="state_override", value="live"))
    await db_session.commit()
    locked_join = await client.post("/api/v1/teams/join", json={"name": "Locked", "secret": created["join_secret"]}, headers={"X-CSRF-Token": client.cookies["csrf_token"]})
    assert locked_join.status_code == 403
    admin_client = await new_client()
    await login(admin_client, admin)
    admin_token = admin_client.cookies["csrf_token"]
    replaced = await admin_client.post(
        f"/api/v1/teams/admin/{created['team']['id']}/replace-member",
        json={"outgoing_user_id": str(outgoing.id), "incoming_user_id": str(incoming.id)},
        headers={"X-CSRF-Token": admin_token},
    )
    assert replaced.status_code == 200, replaced.text
    assert str(incoming.id) in replaced.text
    await member_client.aclose()
    await admin_client.aclose()


@pytest.mark.asyncio
async def test_crossing_join_and_kick_have_no_deadlock_or_500(db_session, client, redis_client, monkeypatch):
    monkeypatch.setattr(settings, "login_ip_limit", 100)
    monkeypatch.setattr(settings, "join_ip_limit", 100)
    captain_a = await make_user(db_session, "captain")
    captain_b = await make_user(db_session, "captain")
    target = await make_user(db_session, "target")
    await login(client, captain_a)
    team_a = await create_team(client, "Cross A")
    other_client = await new_client()
    await login(other_client, captain_b)
    team_b = await create_team(other_client, "Cross B")
    target_client = await new_client()
    await login(target_client, target)
    joined_b = await target_client.post(
        "/api/v1/teams/join",
        json={"name": "Cross B", "secret": team_b["join_secret"]},
        headers={"X-CSRF-Token": target_client.cookies["csrf_token"]},
    )
    assert joined_b.status_code == 200

    concurrent_clients = await make_isolated_clients(2, redis_client)
    try:
        await asyncio.gather(login(concurrent_clients[0], captain_a), login(concurrent_clients[1], target))
        barrier = asyncio.Barrier(2)

        async def kick() -> int:
            await barrier.wait()
            response = await concurrent_clients[0].post(
                f"/api/v1/teams/{team_a['team']['id']}/kick",
                json={"user_id": str(target.id)},
                headers={"X-CSRF-Token": concurrent_clients[0].cookies["csrf_token"]},
            )
            return response.status_code

        async def join() -> int:
            await barrier.wait()
            response = await concurrent_clients[1].post(
                "/api/v1/teams/join",
                json={"name": "Cross A", "secret": team_a["join_secret"]},
                headers={"X-CSRF-Token": concurrent_clients[1].cookies["csrf_token"]},
            )
            return response.status_code

        statuses = await asyncio.wait_for(asyncio.gather(kick(), join()), timeout=5)
        assert all(status < 500 for status in statuses)
        assert sorted(statuses) == [404, 409]
    finally:
        await asyncio.gather(*(item.aclose() for item in concurrent_clients))
        await app.state.team_test_engine.dispose()
        app.dependency_overrides.clear()
        await target_client.aclose()
        await other_client.aclose()


async def run_parallel_joins(team_name: str, secret: str, users: list[User], redis_client) -> list[int]:
    clients = await make_isolated_clients(len(users), redis_client)
    try:
        await asyncio.gather(*(login(client, user) for client, user in zip(clients, users)))
        barrier = asyncio.Barrier(len(clients))

        async def join(client: AsyncClient) -> int:
            await barrier.wait()
            return (await client.post("/api/v1/teams/join", json={"name": team_name, "secret": secret}, headers={"X-CSRF-Token": client.cookies["csrf_token"]})).status_code

        return await asyncio.gather(*(join(client) for client in clients))
    finally:
        await asyncio.gather(*(client.aclose() for client in clients))
        await app.state.team_test_engine.dispose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_concurrent_joins_enforce_capacity(db_session, client, redis_client, monkeypatch):
    monkeypatch.setattr(settings, "login_ip_limit", 100)
    monkeypatch.setattr(settings, "join_ip_limit", 100)
    monkeypatch.setattr(teams_api, "verify_password", lambda *_args: True)
    captain = await make_user(db_session, "captain")
    first = await make_user(db_session, "member")
    second = await make_user(db_session, "member")
    await login(client, captain)
    created = await create_team(client, "Concurrent")
    for user in (first, second):
        member_client = await new_client()
        await login(member_client, user)
        await member_client.post("/api/v1/teams/join", json={"name": "Concurrent", "secret": created["join_secret"]}, headers={"X-CSRF-Token": member_client.cookies["csrf_token"]})
        await member_client.aclose()
    count_barrier = asyncio.Barrier(20)

    async def synchronized_team_size(session):
        try:
            await asyncio.wait_for(count_barrier.wait(), timeout=0.5)
        except (TimeoutError, asyncio.BrokenBarrierError):
            pass
        return 4

    monkeypatch.setattr(teams_api, "_team_size", synchronized_team_size)
    contenders = [await make_user(db_session, "contender") for _ in range(20)]
    statuses = await run_parallel_joins("Concurrent", created["join_secret"], contenders, redis_client)
    assert statuses.count(200) == 1
    assert statuses.count(409) == 19


@pytest.mark.asyncio
async def test_concurrent_creates_use_advisory_max_team_lock(db_session, redis_client, monkeypatch):
    monkeypatch.setattr(settings, "login_ip_limit", 100)
    await db_session.merge(Config(key="max_teams", value="1"))
    await db_session.commit()
    users = [await make_user(db_session, "creator") for _ in range(5)]
    clients = await make_isolated_clients(len(users), redis_client)
    try:
        await asyncio.gather(*(login(client, user) for client, user in zip(clients, users)))
        count_barrier = asyncio.Barrier(5)

        async def synchronized_max_teams(session):
            try:
                await asyncio.wait_for(count_barrier.wait(), timeout=0.5)
            except (TimeoutError, asyncio.BrokenBarrierError):
                pass
            return 1

        monkeypatch.setattr(teams_api, "_max_teams", synchronized_max_teams)

        async def create(client: AsyncClient, index: int) -> int:
            return (await client.post("/api/v1/teams", json={"name": f"Race-{index}"}, headers={"X-CSRF-Token": client.cookies["csrf_token"]})).status_code

        statuses = await asyncio.gather(*(create(client, i) for i, client in enumerate(clients)))
        assert statuses.count(201) == 1
        assert statuses.count(409) == 4
    finally:
        await asyncio.gather(*(client.aclose() for client in clients))
        await app.state.team_test_engine.dispose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_one_user_parallel_join_to_two_teams_succeeds_once(db_session, client, redis_client, monkeypatch):
    monkeypatch.setattr(settings, "login_ip_limit", 100)
    monkeypatch.setattr(settings, "join_ip_limit", 100)
    monkeypatch.setattr(teams_api, "verify_password", lambda *_args: True)
    captains = [await make_user(db_session, "captain") for _ in range(2)]
    await login(client, captains[0])
    first = await create_team(client, "First")
    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": client.cookies["csrf_token"]})
    second_client = await new_client()
    await login(second_client, captains[1])
    second = await create_team(second_client, "Second")
    await second_client.aclose()
    joining_user = await make_user(db_session, "joiner")
    clients = await make_isolated_clients(2, redis_client)
    try:
        await asyncio.gather(*(login(c, joining_user) for c in clients))
        count_barrier = asyncio.Barrier(2)

        async def synchronized_team_size(session):
            try:
                await asyncio.wait_for(count_barrier.wait(), timeout=0.5)
            except (TimeoutError, asyncio.BrokenBarrierError):
                pass
            return 4

        monkeypatch.setattr(teams_api, "_team_size", synchronized_team_size)

        async def join(c: AsyncClient, team: dict) -> int:
            return (await c.post("/api/v1/teams/join", json={"name": team["team"]["name"], "secret": team["join_secret"]}, headers={"X-CSRF-Token": c.cookies["csrf_token"]})).status_code

        statuses = await asyncio.gather(join(clients[0], first), join(clients[1], second))
        assert sorted(statuses) == [200, 409]
    finally:
        await asyncio.gather(*(c.aclose() for c in clients))
        await app.state.team_test_engine.dispose()
        app.dependency_overrides.clear()
