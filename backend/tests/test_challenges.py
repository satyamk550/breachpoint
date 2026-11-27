import uuid

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.challenge import Category, Challenge, Flag, Solve, Tag
from app.models.config import Config
from app.models.team import Team
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
    await db_session.execute(delete(AuditLog))
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


async def put_in_team(db_session, player: User) -> Team:
    team = Team(
        name=f"T-{uuid.uuid4().hex[:8]}",
        join_secret_hash=hash_password(PASSWORD),
        captain_id=player.id,
    )
    db_session.add(team)
    await db_session.flush()
    player.team_id = team.id
    await db_session.commit()
    return team


@pytest.mark.asyncio
async def test_player_eligibility_states_and_no_team(client, db_session):
    admin, player, player_client, category = await setup(client, db_session)
    await create_challenge(client, category.id)
    hidden = await create_challenge(client, category.id, "Hidden", "hidden")
    draft = await create_challenge(client, category.id, "Draft", "draft")
    assert (await player_client.get("/api/v1/challenges")).status_code == 403
    await put_in_team(db_session, player)
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
    team = await put_in_team(db_session, player)
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
async def test_wrong_event_state_for_challenges_is_403(client, db_session):
    _, player, player_client, category = await setup(client, db_session)
    await put_in_team(db_session, player)
    await db_session.merge(Config(key="state_override", value="draft_upcoming"))
    await db_session.commit()
    response = await player_client.get("/api/v1/challenges")
    assert response.status_code == 403
    assert "can_view_challenges" in response.json()["detail"]
    await player_client.aclose()


@pytest.mark.asyncio
async def test_locked_challenge_is_404_and_absent_from_list(client, db_session):
    _, player, player_client, category = await setup(client, db_session)
    prerequisite = await create_challenge(client, category.id, "Prerequisite")
    locked = await create_challenge(
        client, category.id, "Locked", prerequisites=[prerequisite["id"]]
    )
    await put_in_team(db_session, player)
    listing = await player_client.get("/api/v1/challenges")
    assert listing.status_code == 200
    assert "Locked" not in listing.text
    assert (await player_client.get(f"/api/v1/challenges/{locked['id']}")).status_code == 404
    await player_client.aclose()


@pytest.mark.asyncio
async def test_self_reference_and_three_node_cycle_are_rejected(client, db_session):
    _, _, _, category = await setup(client, db_session)
    first = await create_challenge(client, category.id, "Cycle A")
    second = await create_challenge(client, category.id, "Cycle B")
    third = await create_challenge(client, category.id, "Cycle C")
    headers = {"X-CSRF-Token": client.cookies["csrf_token"]}
    self_ref = await client.patch(
        f"/api/v1/admin/challenges/{first['id']}",
        json={"prerequisites": [first["id"]]},
        headers=headers,
    )
    assert self_ref.status_code == 422
    assert (
        await client.patch(
            f"/api/v1/admin/challenges/{first['id']}",
            json={"prerequisites": [second["id"]]},
            headers=headers,
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/admin/challenges/{second['id']}",
            json={"prerequisites": [first["id"]]},
            headers=headers,
        )
    ).status_code == 422
    assert (
        await client.patch(
            f"/api/v1/admin/challenges/{second['id']}",
            json={"prerequisites": [third["id"]]},
            headers=headers,
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/admin/challenges/{third['id']}",
            json={"prerequisites": [first["id"]]},
            headers=headers,
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_regex_length_validation_is_explicit(client, db_session):
    _, _, _, category = await setup(client, db_session)
    challenge = await create_challenge(client, category.id, "Regex validation")
    headers = {"X-CSRF-Token": client.cookies["csrf_token"]}
    exact_200 = "a" * 200
    accepted = await client.post(
        f"/api/v1/admin/challenges/{challenge['id']}/flags",
        json={"type": "regex", "content": exact_200},
        headers=headers,
    )
    assert accepted.status_code == 201
    normal = r"^FLAG\{[a-z0-9_]+\}$"
    normal_response = await client.post(
        f"/api/v1/admin/challenges/{challenge['id']}/flags",
        json={"type": "regex", "content": normal},
        headers=headers,
    )
    assert normal_response.status_code == 201
    static_500 = await client.post(
        f"/api/v1/admin/challenges/{challenge['id']}/flags",
        json={"type": "static", "content": "s" * 500},
        headers=headers,
    )
    assert static_500.status_code == 201
    static_501_pattern = "s" * 501
    static_501 = await client.post(
        f"/api/v1/admin/challenges/{challenge['id']}/flags",
        json={"type": "static", "content": static_501_pattern},
        headers=headers,
    )
    assert static_501.status_code == 422
    invalid = await client.post(
        f"/api/v1/admin/challenges/{challenge['id']}/flags",
        json={"type": "regex", "content": "["},
        headers=headers,
    )
    assert invalid.status_code == 422
    too_long_pattern = "a" * 201
    too_long = await client.post(
        f"/api/v1/admin/challenges/{challenge['id']}/flags",
        json={"type": "regex", "content": too_long_pattern},
        headers=headers,
    )
    assert too_long.status_code == 422
    assert "regex flag patterns must be 200 characters or fewer" in too_long.text
    assert too_long_pattern not in too_long.text
    nested_pattern = "(a+)+$"
    nested = await client.post(
        f"/api/v1/admin/challenges/{challenge['id']}/flags",
        json={"type": "regex", "content": nested_pattern},
        headers=headers,
    )
    assert nested.status_code == 422
    assert "regex flag pattern is too expensive to match" in nested.text
    assert nested_pattern not in nested.text
    update_target = await client.post(
        f"/api/v1/admin/challenges/{challenge['id']}/flags",
        json={"type": "static", "content": "safe-static"},
        headers=headers,
    )
    assert update_target.status_code == 201
    update_flag_id = update_target.json()["id"]
    edit_200 = await client.patch(
        f"/api/v1/admin/challenges/{challenge['id']}/flags/{update_flag_id}",
        json={"type": "regex", "content": exact_200},
        headers=headers,
    )
    assert edit_200.status_code == 200
    edit_201_pattern = "b" * 201
    edit_201 = await client.patch(
        f"/api/v1/admin/challenges/{challenge['id']}/flags/{update_flag_id}",
        json={"type": "regex", "content": edit_201_pattern},
        headers=headers,
    )
    assert edit_201.status_code == 422
    assert "regex flag patterns must be 200 characters or fewer" in edit_201.text
    assert edit_201_pattern not in edit_201.text
    assert (
        await client.patch(
            f"/api/v1/admin/challenges/{challenge['id']}/flags/{update_flag_id}",
            json={"type": "regex", "content": nested_pattern},
            headers=headers,
        )
    ).status_code == 422
    for pattern in (too_long_pattern, nested_pattern, edit_201_pattern, static_501_pattern):
        assert pattern not in too_long.text
        assert pattern not in nested.text
        assert pattern not in static_501.text
    rows = (await db_session.scalars(select(AuditLog))).all()
    assert all(
        pattern not in str(row.meta)
        for row in rows
        for pattern in (too_long_pattern, nested_pattern, edit_201_pattern, static_501_pattern)
    )


@pytest.mark.asyncio
async def test_numeric_validation_each_case_is_rejected(client, db_session):
    _, _, _, category = await setup(client, db_session)
    headers = {"X-CSRF-Token": client.cookies["csrf_token"]}
    cases = [
        {"points": -1},
        {"scoring_mode": "dynamic", "initial": 1, "minimum": 2},
        {"scoring_mode": "dynamic", "decay": 0},
        {"max_attempts": 0},
    ]
    for values in cases:
        payload = {
            "title": f"Validation {uuid.uuid4().hex[:6]}",
            "description_md": "Description",
            "category_id": str(category.id),
        }
        payload.update(values)
        response = await client.post("/api/v1/admin/challenges", json=payload, headers=headers)
        assert response.status_code == 422, values


@pytest.mark.asyncio
async def test_delete_challenge_with_solves_is_409(client, db_session):
    _, player, _, category = await setup(client, db_session)
    challenge = await create_challenge(client, category.id, "Solved")
    team = await put_in_team(db_session, player)
    db_session.add(
        Solve(team_id=team.id, challenge_id=uuid.UUID(challenge["id"]), user_id=player.id)
    )
    await db_session.commit()
    response = await client.delete(
        f"/api/v1/admin/challenges/{challenge['id']}",
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert response.status_code == 409
    assert "hide it instead" in response.json()["detail"]


@pytest.mark.asyncio
async def test_clone_has_no_prerequisites_or_solves(client, db_session):
    _, player, _, category = await setup(client, db_session)
    prerequisite = await create_challenge(client, category.id, "Clone prerequisite")
    source = await create_challenge(
        client, category.id, "Clone source", prerequisites=[prerequisite["id"]]
    )
    team = await put_in_team(db_session, player)
    db_session.add(Solve(team_id=team.id, challenge_id=uuid.UUID(source["id"]), user_id=player.id))
    await db_session.commit()
    clone = await client.post(
        f"/api/v1/admin/challenges/{source['id']}/clone",
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert clone.status_code == 201
    assert clone.json()["visibility"] == "draft"
    assert clone.json()["prerequisites"] == []
    assert clone.json()["solve_count"] == 0


@pytest.mark.asyncio
async def test_admin_matrix_player_unauthenticated_and_csrf(client, db_session):
    _, _, player_client, category = await setup(client, db_session)
    challenge = await create_challenge(client, category.id, "Auth matrix")
    flag = await client.post(
        f"/api/v1/admin/challenges/{challenge['id']}/flags",
        json={"type": "static", "content": "auth-matrix-flag"},
        headers={"X-CSRF-Token": client.cookies["csrf_token"]},
    )
    assert flag.status_code == 201
    flag_id = flag.json()["id"]
    admin_paths = [
        ("GET", "/api/v1/admin/categories", None),
        ("POST", "/api/v1/admin/categories", {"name": "x", "sort_order": 0}),
        ("PATCH", f"/api/v1/admin/categories/{category.id}", {"name": "x", "sort_order": 0}),
        ("DELETE", f"/api/v1/admin/categories/{category.id}", None),
        ("GET", "/api/v1/admin/challenges", None),
        (
            "POST",
            "/api/v1/admin/challenges",
            {"title": "x", "description_md": "x", "category_id": str(category.id)},
        ),
        ("GET", f"/api/v1/admin/challenges/{challenge['id']}", None),
        ("PATCH", f"/api/v1/admin/challenges/{challenge['id']}", {"title": "x"}),
        ("DELETE", f"/api/v1/admin/challenges/{challenge['id']}", None),
        (
            "POST",
            "/api/v1/admin/challenges/visibility",
            {"visibility": "hidden", "challenge_ids": [challenge["id"]]},
        ),
        ("POST", f"/api/v1/admin/challenges/{challenge['id']}/clone", None),
        ("GET", f"/api/v1/admin/challenges/{challenge['id']}/flags", None),
        (
            "POST",
            f"/api/v1/admin/challenges/{challenge['id']}/flags",
            {"type": "static", "content": "x"},
        ),
        (
            "PATCH",
            f"/api/v1/admin/challenges/{challenge['id']}/flags/{flag_id}",
            {"type": "static", "content": "y"},
        ),
        ("DELETE", f"/api/v1/admin/challenges/{challenge['id']}/flags/{flag_id}", None),
    ]
    unauth = type(client)(transport=client._transport, base_url="https://test")
    await unauth.get("/api/v1/health")
    unauth_headers = {"X-CSRF-Token": unauth.cookies["csrf_token"]}
    for method, path, payload in admin_paths:
        player_headers = {"X-CSRF-Token": player_client.cookies["csrf_token"]}
        response = await player_client.request(method, path, json=payload, headers=player_headers)
        assert response.status_code == 403, (method, path, response.text)
        response = await unauth.request(method, path, json=payload, headers=unauth_headers)
        assert response.status_code == 401, (method, path, response.text)
    for method, path, payload in admin_paths:
        if method != "GET":
            response = await client.request(method, path, json=payload)
            assert response.status_code == 403, (method, path, response.text)
    await unauth.aclose()
    await player_client.aclose()


@pytest.mark.asyncio
async def test_audit_rows_exist_and_exclude_static_and_regex_content(client, db_session):
    _, _, _, category = await setup(client, db_session)
    challenge = await create_challenge(client, category.id, "Audit target")
    headers = {"X-CSRF-Token": client.cookies["csrf_token"]}
    category_response = await client.post(
        "/api/v1/admin/categories",
        json={"name": f"Audit category {uuid.uuid4().hex[:6]}", "sort_order": 2},
        headers=headers,
    )
    assert category_response.status_code == 201
    audit_category_id = category_response.json()["id"]
    assert (
        await client.patch(
            f"/api/v1/admin/categories/{audit_category_id}",
            json={"name": f"Audit category updated {uuid.uuid4().hex[:6]}", "sort_order": 3},
            headers=headers,
        )
    ).status_code == 200
    static_text = "STATIC-AUDIT-SECRET"
    regex_text = "REGEX-AUDIT-PATTERN"
    flag_ids = []
    for content, flag_type in ((static_text, "static"), (regex_text, "regex")):
        response = await client.post(
            f"/api/v1/admin/challenges/{challenge['id']}/flags",
            json={"type": flag_type, "content": content},
            headers=headers,
        )
        assert response.status_code == 201
        flag_ids.append(response.json()["id"])
    assert (
        await client.patch(
            f"/api/v1/admin/challenges/{challenge['id']}",
            json={"title": "Audit target updated"},
            headers=headers,
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/admin/challenges/visibility",
            json={"visibility": "hidden", "challenge_ids": [challenge["id"]]},
            headers=headers,
        )
    ).status_code == 200
    clone = await client.post(f"/api/v1/admin/challenges/{challenge['id']}/clone", headers=headers)
    assert clone.status_code == 201
    assert (
        await client.patch(
            f"/api/v1/admin/challenges/{challenge['id']}/flags/{flag_ids[0]}",
            json={"type": "static", "content": static_text},
            headers=headers,
        )
    ).status_code == 200
    assert (
        await client.delete(
            f"/api/v1/admin/challenges/{challenge['id']}/flags/{flag_ids[1]}",
            headers=headers,
        )
    ).status_code == 204
    assert (
        await client.delete(f"/api/v1/admin/challenges/{challenge['id']}", headers=headers)
    ).status_code == 204
    assert (
        await client.delete(f"/api/v1/admin/categories/{audit_category_id}", headers=headers)
    ).status_code == 204
    rows = (await db_session.scalars(select(AuditLog))).all()
    actions = {row.action for row in rows}
    assert "challenge_created" in actions
    assert {
        "category_created",
        "category_updated",
        "category_deleted",
        "challenge_created",
        "challenge_updated",
        "challenge_visibility_changed",
        "challenge_cloned",
        "challenge_deleted",
        "flag_created",
        "flag_updated",
        "flag_deleted",
    } <= actions
    assert all(static_text not in str(row.meta) and regex_text not in str(row.meta) for row in rows)


@pytest.mark.asyncio
async def test_flag_content_never_appears_in_player_or_challenge_read_responses(client, db_session):
    _, player, player_client, category = await setup(client, db_session)
    challenge = await create_challenge(client, category.id, "Leak audit")
    secret = "FLAG-LEAK-PROBE"
    pattern = "^REGEX-LEAK$"
    headers = {"X-CSRF-Token": client.cookies["csrf_token"]}
    for content, flag_type in ((secret, "static"), (pattern, "regex")):
        response = await client.post(
            f"/api/v1/admin/challenges/{challenge['id']}/flags",
            json={"type": flag_type, "content": content},
            headers=headers,
        )
        assert response.status_code == 201
    await put_in_team(db_session, player)
    responses = [
        await player_client.get("/api/v1/challenges"),
        await player_client.get(f"/api/v1/challenges/{challenge['id']}"),
        await client.get("/api/v1/admin/challenges"),
        await client.get(f"/api/v1/admin/challenges/{challenge['id']}"),
    ]
    for response in responses:
        assert secret not in response.text
        assert pattern not in response.text
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
