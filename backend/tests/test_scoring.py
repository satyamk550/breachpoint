import asyncio
# ruff: noqa: E501, I001
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.sql import Select

from app.core.config import settings
from app.core.db import get_session
from app.core.redis import get_redis
from app.core.security import hash_password
from app.main import create_app
from app.models.audit_log import AuditLog
from app.models.challenge import Category, Challenge, Flag, Hint, HintUnlock, Solve
from app.models.config import Config
from app.models.scoring import Award, ScoreEvent, Submission
from app.models.team import Team
from app.models.user import User
from app.services.scoring import current_value

PASSWORD = "correct-horse-1"


@pytest.fixture(autouse=True)
async def scoring_defaults(db_session, redis_client):
    await redis_client.flushdb()
    await db_session.execute(delete(AuditLog))
    await db_session.execute(delete(ScoreEvent))
    await db_session.execute(delete(Submission))
    await db_session.execute(delete(Award))
    await db_session.execute(delete(HintUnlock))
    await db_session.execute(delete(Solve))
    await db_session.execute(delete(Hint))
    await db_session.execute(delete(Flag))
    await db_session.execute(delete(Challenge))
    await db_session.execute(delete(Category))
    await db_session.execute(update(User).values(team_id=None))
    await db_session.execute(delete(Team))
    for key, value in {"event_start": "", "event_end": "", "state_override": "live"}.items():
        await db_session.merge(Config(key=key, value=value))
    await db_session.commit()
    yield


async def make_user(session, name: str, role: str = "player") -> User:
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


async def login(client: AsyncClient, user: User) -> None:
    await client.get("/api/v1/health")
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": PASSWORD},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert response.status_code == 200, response.text


@pytest.fixture
async def isolated_clients(engine, redis_client):
    old_login_limit = settings.login_ip_limit
    settings.login_ip_limit = max(old_login_limit, 100)
    test_app = create_app()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def session_override():
        async with session_factory() as session:
            yield session

    async def redis_override():
        return redis_client

    test_app.dependency_overrides[get_session] = session_override
    test_app.dependency_overrides[get_redis] = redis_override
    transport = ASGITransport(app=test_app)
    clients: list[AsyncClient] = []

    async def factory(user: User) -> AsyncClient:
        client = AsyncClient(transport=transport, base_url="https://test")
        clients.append(client)
        await login(client, user)
        return client

    yield factory
    for client in clients:
        await client.aclose()
    settings.login_ip_limit = old_login_limit


async def create_challenge(client: AsyncClient, category_id, **values):
    payload = {
        "title": f"Challenge {uuid.uuid4().hex[:6]}",
        "description_md": "Description",
        "category_id": str(category_id),
        "points": 100,
        "visibility": "visible",
    }
    payload.update(values)
    response = await client.post(
        "/api/v1/admin/challenges",
        json=payload,
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def add_flag(client: AsyncClient, challenge_id: str, content: str, flag_type="static", **values):
    payload = {"type": flag_type, "content": content, **values}
    response = await client.post(
        f"/api/v1/admin/challenges/{challenge_id}/flags",
        json=payload,
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert response.status_code == 201, response.text


async def add_team(session, user: User) -> Team:
    team = Team(
        name=f"Team {uuid.uuid4().hex[:8]}",
        join_secret_hash=hash_password(PASSWORD),
        captain_id=user.id,
    )
    session.add(team)
    await session.flush()
    user.team_id = team.id
    await session.commit()
    return team


async def setup_users(db_session, isolated_clients, count=1):
    admin = await make_user(db_session, "admin", "admin")
    admin_client = await isolated_clients(admin)
    players = []
    clients = []
    for index in range(count):
        user = await make_user(db_session, f"player{index}")
        players.append(user)
        clients.append(await isolated_clients(user))
    category = Category(name=f"cat-{uuid.uuid4().hex[:8]}", sort_order=1)
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return admin_client, players, clients, category


async def submit_after_barrier(barrier, client, challenge_id, value):
    await barrier.wait()
    return await client.post(
        f"/api/v1/challenges/{challenge_id}/submit",
        json={"value": value},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )


async def unlock_after_barrier(barrier, client, hint_id):
    await barrier.wait()
    return await client.post(
        f"/api/v1/hints/{hint_id}/unlock",
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )


@pytest.mark.asyncio
async def test_submission_correct_incorrect_flags_and_secret_safety(
    db_session, isolated_clients
):
    admin, players, clients, category = await setup_users(db_session, isolated_clients)
    player = players[0]
    await add_team(db_session, player)
    challenge = await create_challenge(admin, category.id, max_attempts=3)
    await add_flag(admin, challenge["id"], "FLAG{secret}")
    secret = "FLAG{secret}"
    incorrect = "FLAG{wrong-secret}"
    headers = {"X-CSRF-Token": clients[0].cookies["csrf_token"]}
    response = await clients[0].post(
        f"/api/v1/challenges/{challenge['id']}/submit",
        json={"value": incorrect},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {"correct": False, "attempts_remaining": 2}
    assert incorrect not in response.text
    response = await clients[0].post(
        f"/api/v1/challenges/{challenge['id']}/submit",
        json={"value": f"  {secret}  "},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["correct"] is True
    assert secret not in response.text
    rows = (await db_session.scalars(select(Submission))).all()
    assert rows[0].provided_value == incorrect
    assert rows[1].provided_value is None
    assert secret not in str(rows)
    await clients[0].aclose()


@pytest.mark.asyncio
async def test_case_insensitive_regex_and_input_validation(db_session, isolated_clients):
    admin, players, clients, category = await setup_users(db_session, isolated_clients)
    await add_team(db_session, players[0])
    challenge = await create_challenge(admin, category.id)
    await add_flag(admin, challenge["id"], "flag{abc}", case_insensitive=True)
    assert (
        await clients[0].post(
            f"/api/v1/challenges/{challenge['id']}/submit",
            json={"value": " FLAG{ABC} "},
            headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
        )
    ).json()["correct"] is True
    regex_challenge = await create_challenge(admin, category.id)
    await add_flag(admin, regex_challenge["id"], r"^FLAG\{[a-z0-9_]+\}$", "regex")
    response = await clients[0].post(
        f"/api/v1/challenges/{regex_challenge['id']}/submit",
        json={"value": "FLAG{team_1}"},
        headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
    )
    assert response.json()["correct"] is True
    response = await clients[0].post(
        f"/api/v1/challenges/{regex_challenge['id']}/submit",
        json={"value": "x" * 501},
        headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
    )
    assert response.status_code == 422
    assert "x" * 501 not in response.text


@pytest.mark.asyncio
async def test_submission_order_hidden_locked_no_team_and_lifecycle(
    db_session, isolated_clients
):
    admin, players, clients, category = await setup_users(db_session, isolated_clients, 1)
    visible = await create_challenge(admin, category.id)
    hidden = await create_challenge(admin, category.id, visibility="hidden")
    locked = await create_challenge(admin, category.id, prerequisites=[visible["id"]])
    for challenge_id, expected_status in ((hidden["id"], 404), (locked["id"], 403)):
        response = await clients[0].post(
            f"/api/v1/challenges/{challenge_id}/submit",
            json={"value": "x"},
            headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
        )
        assert response.status_code == expected_status
    await add_team(db_session, players[0])
    for challenge_id in (hidden["id"], locked["id"]):
        response = await clients[0].post(
            f"/api/v1/challenges/{challenge_id}/submit",
            json={"value": "x"},
            headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
        )
        assert response.status_code == 404
    for state in ("draft_upcoming", "paused", "ended"):
        await db_session.merge(Config(key="state_override", value=state))
        await db_session.commit()
        response = await clients[0].post(
            f"/api/v1/challenges/{visible['id']}/submit",
            json={"value": "x"},
            headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
        )
        assert response.status_code == 403
        assert "can_submit" in response.text
    await db_session.merge(Config(key="state_override", value="live"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_visible_submission_without_team_is_forbidden(db_session, isolated_clients):
    admin, players, clients, category = await setup_users(db_session, isolated_clients)
    challenge = await create_challenge(admin, category.id)
    response = await clients[0].post(
        f"/api/v1/challenges/{challenge['id']}/submit",
        json={"value": "candidate"},
        headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["draft_upcoming", "paused", "ended"])
async def test_each_non_live_state_forbids_submission_without_flag_check(
    db_session, isolated_clients, monkeypatch, state
):
    admin, players, clients, category = await setup_users(db_session, isolated_clients)
    await add_team(db_session, players[0])
    challenge = await create_challenge(admin, category.id)
    await add_flag(admin, challenge["id"], "should-not-be-checked")
    await db_session.merge(Config(key="state_override", value=state))
    await db_session.commit()

    import app.api.v1.scoring as scoring_api

    monkeypatch.setattr(scoring_api, "_flag_matches", lambda *_: pytest.fail("flag check reached"))
    response = await clients[0].post(
        f"/api/v1/challenges/{challenge['id']}/submit",
        json={"value": "candidate"},
        headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
    )
    assert response.status_code == 403
    assert await db_session.scalar(select(func.count(Submission.id))) == 0


@pytest.mark.asyncio
async def test_regex_timeout_is_incorrect_without_hanging(db_session, isolated_clients, monkeypatch):
    admin, players, clients, category = await setup_users(db_session, isolated_clients)
    await add_team(db_session, players[0])
    challenge = await create_challenge(admin, category.id)
    db_session.add(
        Flag(
            challenge_id=uuid.UUID(challenge["id"]),
            type="regex",
            content=r"^(a+)+$",
        )
    )
    await db_session.commit()
    import app.api.v1.scoring as scoring_api

    class TimedOutMatch:
        def fullmatch(self, value, timeout):
            raise TimeoutError

    monkeypatch.setattr(scoring_api.regex, "compile", lambda *args, **kwargs: TimedOutMatch())
    response = await clients[0].post(
        f"/api/v1/challenges/{challenge['id']}/submit",
        json={"value": "candidate"},
        headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
    )
    assert response.status_code == 200
    assert response.json()["correct"] is False


@pytest.mark.asyncio
async def test_submission_and_flag_secrecy_in_logs(db_session, isolated_clients, caplog):
    admin, players, clients, category = await setup_users(db_session, isolated_clients)
    await add_team(db_session, players[0])
    challenge = await create_challenge(admin, category.id)
    secret = "FLAG{log-secret}"
    submitted = "FLAG{log-submitted}"
    await add_flag(admin, challenge["id"], secret)
    response = await clients[0].post(
        f"/api/v1/challenges/{challenge['id']}/submit",
        json={"value": submitted},
        headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]},
    )
    assert response.status_code == 200
    assert secret not in caplog.text
    assert submitted not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/v1/admin/awards", {"name": "x", "value": 1, "reason": "x"}),
        ("delete", "/api/v1/admin/awards/00000000-0000-0000-0000-000000000000", None),
        ("get", "/api/v1/admin/submissions", None),
        ("get", "/api/v1/admin/solves", None),
        ("post", "/api/v1/admin/solves/00000000-0000-0000-0000-000000000000/adjust", {"action": "delete", "reason": "x"}),
    ],
)
async def test_every_new_admin_endpoint_requires_auth_and_csrf(
    db_session, isolated_clients, method, path, payload
):
    admin, players, clients, category = await setup_users(db_session, isolated_clients)
    team = await add_team(db_session, players[0])
    if method == "post" and path == "/api/v1/admin/awards":
        payload = {**payload, "team_id": str(team.id)}
    player_response = await getattr(clients[0], method)(path, json=payload) if payload else await getattr(clients[0], method)(path)
    assert player_response.status_code == 403
    unauth = AsyncClient(transport=clients[0]._transport, base_url="https://test")
    await unauth.get("/api/v1/health")
    unauth_response = await getattr(unauth, method)(
        path,
        json=payload,
        headers={"X-CSRF-Token": unauth.cookies["csrf_token"]},
    ) if payload else await getattr(unauth, method)(
        path,
        headers={"X-CSRF-Token": unauth.cookies["csrf_token"]},
    )
    assert unauth_response.status_code == 401
    await unauth.aclose()
    missing_csrf = await getattr(admin, method)(path, json=payload) if payload else await getattr(admin, method)(path)
    if method in {"post", "delete"}:
        assert missing_csrf.status_code == 403
    else:
        assert missing_csrf.status_code == 200


def test_score_events_have_no_update_or_delete_path():
    source = __import__("pathlib").Path(__file__).parents[1] / "app" / "api" / "v1" / "scoring.py"
    text = source.read_text(encoding="utf-8")
    assert "delete(ScoreEvent" not in text
    assert "update(ScoreEvent" not in text


@pytest.mark.asyncio
async def test_already_solved_max_attempts_rate_limit_and_auth(
    db_session, redis_client, isolated_clients
):
    admin, players, clients, category = await setup_users(db_session, isolated_clients, 1)
    await add_team(db_session, players[0])
    challenge = await create_challenge(admin, category.id, max_attempts=1)
    await add_flag(admin, challenge["id"], "correct")
    headers = {"X-CSRF-Token": clients[0].cookies["csrf_token"]}
    first = await clients[0].post(f"/api/v1/challenges/{challenge['id']}/submit", json={"value": "wrong"}, headers=headers)
    assert first.status_code == 200
    limited = await clients[0].post(f"/api/v1/challenges/{challenge['id']}/submit", json={"value": "wrong"}, headers=headers)
    assert limited.status_code == 429
    assert limited.json()["detail"]["attempts_used"] == 1
    await db_session.execute(delete(Submission))
    await db_session.commit()
    await clients[0].post(f"/api/v1/challenges/{challenge['id']}/submit", json={"value": "correct"}, headers=headers)
    solved = await clients[0].post(f"/api/v1/challenges/{challenge['id']}/submit", json={"value": "correct"}, headers=headers)
    assert solved.status_code == 409
    assert solved.json()["detail"] == "already solved"
    monkey = settings.submit_attempt_limit
    settings.submit_attempt_limit = 1
    try:
        another = await create_challenge(admin, category.id)
        await add_flag(admin, another["id"], "other")
        await redis_client.delete(f"rate:submit:user:{players[0].id}")
        first = await clients[0].post(f"/api/v1/challenges/{another['id']}/submit", json={"value": "x"}, headers=headers)
        second = await clients[0].post(f"/api/v1/challenges/{another['id']}/submit", json={"value": "y"}, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 429
        assert "Retry-After" in second.headers
    finally:
        settings.submit_attempt_limit = monkey
    unauth = AsyncClient(transport=clients[0]._transport, base_url="https://test")
    response = await unauth.post(f"/api/v1/challenges/{challenge['id']}/submit", json={"value": "x"})
    assert response.status_code == 403
    await unauth.aclose()


def test_current_value_formulas():
    static = Challenge(points=125, scoring_mode="static", initial=125, minimum=0, decay=1, function="linear")
    assert current_value(static, 0) == 125
    linear = Challenge(points=0, scoring_mode="dynamic", initial=100, minimum=40, decay=30, function="linear")
    assert [current_value(linear, count) for count in (1, 2, 3, 4)] == [100, 70, 40, 40]
    logarithmic = Challenge(points=0, scoring_mode="dynamic", initial=100, minimum=40, decay=2, function="logarithmic")
    assert current_value(logarithmic, 1) == 100
    assert current_value(logarithmic, 2) == 85
    assert current_value(logarithmic, 100) == 40


@pytest.mark.asyncio
async def test_score_projection_dynamic_drop_hints_awards_and_floor(db_session, isolated_clients):
    admin, players, clients, category = await setup_users(db_session, isolated_clients, 2)
    teams = [await add_team(db_session, player) for player in players]
    challenge = await create_challenge(admin, category.id, scoring_mode="dynamic", initial=100, minimum=40, decay=30, function="linear")
    await add_flag(admin, challenge["id"], "flag")
    response = await clients[0].post(f"/api/v1/challenges/{challenge['id']}/submit", json={"value": "flag"}, headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]})
    assert response.status_code == 200
    assert (await clients[0].get("/api/v1/teams/me/score")).json()["score"] == 100
    response = await clients[1].post(f"/api/v1/challenges/{challenge['id']}/submit", json={"value": "flag"}, headers={"X-CSRF-Token": clients[1].cookies["csrf_token"]})
    assert response.status_code == 200
    score = await clients[0].get("/api/v1/teams/me/score")
    assert score.status_code == 200
    assert score.json()["score"] == 70
    challenge_read = await clients[0].get(f"/api/v1/challenges/{challenge['id']}")
    assert challenge_read.json()["solve_count"] == 2
    assert challenge_read.json()["current_value"] == 70
    hint_response = await admin.post(f"/api/v1/admin/challenges/{challenge['id']}/hints", json={"content": "hint", "cost": 80}, headers={"X-CSRF-Token": admin.cookies["csrf_token"]})
    hint_id = hint_response.json()["id"]
    await db_session.merge(Config(key="state_override", value="live"))
    await db_session.commit()
    first = await clients[0].post(f"/api/v1/hints/{hint_id}/unlock", headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]})
    second = await clients[0].post(f"/api/v1/hints/{hint_id}/unlock", headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]})
    assert first.status_code == 200 and second.status_code == 200
    assert (await clients[0].get("/api/v1/teams/me/score")).json()["score"] == 0
    concurrent_hint = await admin.post(f"/api/v1/admin/challenges/{challenge['id']}/hints", json={"content": "another hint", "cost": 1}, headers={"X-CSRF-Token": admin.cookies["csrf_token"]})
    concurrent_hint_id = concurrent_hint.json()["id"]
    await db_session.execute(update(User).where(User.id == players[1].id).values(team_id=teams[0].id))
    await db_session.commit()
    hint_barrier = asyncio.Barrier(2)
    unlocks = await asyncio.gather(
        *[unlock_after_barrier(hint_barrier, client, concurrent_hint_id) for client in clients]
    )
    assert all(unlock.status_code == 200 for unlock in unlocks)
    assert await db_session.scalar(select(func.count(ScoreEvent.id)).where(ScoreEvent.kind == "hint")) == 2
    award = await admin.post("/api/v1/admin/awards", json={"team_id": str(teams[0].id), "name": "penalty", "value": -100, "reason": "test"}, headers={"X-CSRF-Token": admin.cookies["csrf_token"]})
    assert award.status_code == 201
    award_events = (await db_session.scalars(select(ScoreEvent).where(ScoreEvent.kind == "award"))).all()
    assert [event.delta for event in award_events] == [-100]
    assert (await clients[0].get("/api/v1/teams/me/score")).json()["score"] == 0
    deleted = await admin.delete(f"/api/v1/admin/awards/{award.json()['id']}", headers={"X-CSRF-Token": admin.cookies["csrf_token"]})
    assert deleted.status_code == 204
    award_events = (await db_session.scalars(select(ScoreEvent).where(ScoreEvent.kind == "award"))).all()
    assert [event.delta for event in award_events] == [-100, 100]


@pytest.mark.asyncio
async def test_first_blood_and_teammate_races_have_one_row_and_event(db_session, isolated_clients):
    admin, players, clients, category = await setup_users(db_session, isolated_clients, 10)
    teams = [await add_team(db_session, player) for player in players]
    challenge = await create_challenge(admin, category.id)
    await add_flag(admin, challenge["id"], "race")
    race_barrier = asyncio.Barrier(10)
    responses = await asyncio.gather(
        *[submit_after_barrier(race_barrier, client, challenge["id"], "race") for client in clients]
    )
    assert sum(response.status_code == 200 for response in responses) == 10
    assert sum(response.json().get("correct") is True for response in responses) == 10
    assert await db_session.scalar(select(func.count(Solve.id))) == 10
    assert await db_session.scalar(select(func.count(Solve.id)).where(Solve.is_first_blood.is_(True))) == 1
    assert await db_session.scalar(select(func.count(ScoreEvent.id)).where(ScoreEvent.kind == "solve")) == 10
    teammate_challenge = await create_challenge(admin, category.id)
    await add_flag(admin, teammate_challenge["id"], "teammate-race")
    await db_session.execute(update(User).where(User.id.in_([player.id for player in players])).values(team_id=teams[0].id))
    await db_session.commit()
    teammate_barrier = asyncio.Barrier(10)
    teammate_responses = await asyncio.gather(
        *[submit_after_barrier(teammate_barrier, client, teammate_challenge["id"], "teammate-race") for client in clients]
    )
    assert sum(response.status_code == 200 for response in teammate_responses) == 1
    assert sum(response.status_code == 409 for response in teammate_responses) == 9
    assert await db_session.scalar(select(func.count(Solve.id)).where(Solve.challenge_id == teammate_challenge["id"])) == 1
    assert await db_session.scalar(select(func.count(ScoreEvent.id)).where(ScoreEvent.challenge_id == teammate_challenge["id"])) == 1


@pytest.mark.asyncio
async def test_teammate_race_without_challenge_lock_uses_integrity_error_path(
    db_session, isolated_clients, monkeypatch
):
    admin, players, clients, category = await setup_users(db_session, isolated_clients, 10)
    team = await add_team(db_session, players[0])
    await db_session.execute(update(User).where(User.id.in_([player.id for player in players])).values(team_id=team.id))
    await db_session.commit()
    challenge = await create_challenge(admin, category.id)
    await add_flag(admin, challenge["id"], "integrity-race")
    monkeypatch.setattr(Select, "with_for_update", lambda self, **kwargs: self)
    barrier = asyncio.Barrier(10)
    results = await asyncio.gather(
        *[submit_after_barrier(barrier, client, challenge["id"], "integrity-race") for client in clients],
        return_exceptions=True,
    )
    assert not any(isinstance(result, BaseException) for result in results)
    assert sum(result.status_code == 200 for result in results) == 1
    assert sum(result.status_code == 409 and result.json()["detail"] == "already solved" for result in results) == 9
    assert await db_session.scalar(select(func.count(Solve.id)).where(Solve.challenge_id == challenge["id"])) == 1
    assert await db_session.scalar(select(func.count(ScoreEvent.id)).where(ScoreEvent.challenge_id == challenge["id"])) == 1


@pytest.mark.asyncio
async def test_admin_filters_adjustment_and_secrecy(db_session, isolated_clients):
    admin, players, clients, category = await setup_users(db_session, isolated_clients, 1)
    await add_team(db_session, players[0])
    challenge = await create_challenge(admin, category.id)
    await add_flag(admin, challenge["id"], "admin-secret")
    submitted_value = "submitted-secret-" * 15
    await clients[0].post(f"/api/v1/challenges/{challenge['id']}/submit", json={"value": submitted_value}, headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]})
    submissions = await admin.get("/api/v1/admin/submissions", params={"correct": "false"})
    assert submissions.status_code == 200
    assert submissions.json()[0]["provided_value"] == submitted_value[:200]
    assert "admin-secret" not in submissions.text
    solve_response = await clients[0].post(f"/api/v1/challenges/{challenge['id']}/submit", json={"value": "admin-secret"}, headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]})
    assert solve_response.status_code == 200
    solves = await admin.get("/api/v1/admin/solves")
    assert solves.status_code == 200
    adjust = await admin.post(
        f"/api/v1/admin/solves/{solves.json()[0]['id']}/adjust",
        json={"action": "delete", "reason": "test adjustment"},
        headers={"X-CSRF-Token": admin.cookies["csrf_token"]},
    )
    assert adjust.status_code == 204
    rows = (await db_session.scalars(select(AuditLog))).all()
    events = (await db_session.scalars(select(ScoreEvent))).all()
    assert all(submitted_value not in str(row.meta) for row in rows)
    assert all(submitted_value not in str(event) for event in events)
    assert all("admin-secret" not in str(row.meta) for row in rows)
    assert all("admin-secret" not in str(event) for event in events)
    player_admin_response = await clients[0].get("/api/v1/admin/submissions")
    assert player_admin_response.status_code == 403
    unauth = AsyncClient(transport=clients[0]._transport, base_url="https://test")
    assert (await unauth.get("/api/v1/admin/submissions")).status_code == 401
    await unauth.aclose()
    award = await admin.post("/api/v1/admin/awards", json={"team_id": str(players[0].team_id), "name": "auth", "value": 1, "reason": "auth"}, headers={"X-CSRF-Token": admin.cookies["csrf_token"]})
    assert award.status_code == 201
    assert (await clients[0].delete(f"/api/v1/admin/awards/{award.json()['id']}", headers={"X-CSRF-Token": clients[0].cookies["csrf_token"]})).status_code == 403
    assert (await admin.delete(f"/api/v1/admin/awards/{award.json()['id']}")).status_code == 403
