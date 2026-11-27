# ruff: noqa: E501, I001

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_capability, require_user
from app.core.client_ip import get_client_ip
from app.core.config import settings
from app.core.db import get_session
from app.core.redis import get_redis
from app.core.security import DUMMY_PASSWORD_HASH, hash_password, new_token, verify_password
from app.models.audit_log import AuditLog
from app.models.config import Config
from app.models.team import Team
from app.models.user import User
from app.schemas.teams import (
    AdminMoveUserRequest,
    AdminReplaceMemberRequest,
    AdminTeamEditRequest,
    TeamCreateRequest,
    TeamJoinRequest,
    TeamMemberResponse,
    TeamRenameRequest,
    TeamResponse,
    TeamSecretResponse,
    TeamSummary,
    UserTargetRequest,
)
from app.schemas.scoring import TeamScoreResponse, SolvedChallengeResponse
from app.services.scoring import current_value, team_score
from app.models.challenge import Challenge, Solve
from app.services.lifecycle import read_lifecycle_config

router = APIRouter(prefix="/teams", tags=["teams"])
ADVISORY_LOCK_KEY = 31003


async def _limit(redis: Redis, key: str, limit: int) -> None:
    pipe = redis.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, settings.join_window_seconds)
    count, _ = await pipe.execute()
    if int(count) > limit:
        retry_after = await redis.ttl(key)
        error = HTTPException(status_code=429, detail="Too many join attempts")
        error.headers = {"Retry-After": str(max(1, retry_after))}
        raise error


async def _team_size(session: AsyncSession) -> int:
    await read_lifecycle_config(session)
    row = await session.get(Config, "team_size")
    return int(row.value) if row else 4


async def _max_teams(session: AsyncSession) -> int:
    row = await session.get(Config, "max_teams")
    return int(row.value) if row else 25


async def _members(session: AsyncSession, team_id: uuid.UUID) -> list[User]:
    return list((await session.scalars(select(User).where(User.team_id == team_id).order_by(User.created_at, User.id))).all())


async def _response(session: AsyncSession, team: Team, *, include_members: bool = True) -> TeamResponse:
    members = await _members(session, team.id) if include_members else []
    count = len(members) if include_members else await session.scalar(select(func.count(User.id)).where(User.team_id == team.id))
    return TeamResponse(
        id=team.id, name=team.name, member_count=int(count or 0), captain_id=team.captain_id,
        is_banned=team.is_banned, is_hidden=team.is_hidden, created_at=team.created_at,
        members=[TeamMemberResponse.model_validate(member) for member in members],
    )


async def _public_summary(session: AsyncSession, team: Team) -> TeamSummary:
    count = await session.scalar(select(func.count(User.id)).where(User.team_id == team.id))
    return TeamSummary(id=team.id, name=team.name, member_count=int(count or 0))


async def _team_or_404(session: AsyncSession, team_id: uuid.UUID, *, lock: bool = False) -> Team:
    query = select(Team).where(Team.id == team_id)
    if lock:
        query = query.with_for_update()
    team = await session.scalar(query)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


async def _audit(session: AsyncSession, actor: User, action: str, team_id: uuid.UUID, meta: dict) -> None:
    session.add(AuditLog(actor_id=actor.id, action=action, target=f"team:{team_id}", meta=meta))


def _captain_only(team: Team, user: User) -> None:
    if team.captain_id != user.id:
        raise HTTPException(status_code=403, detail="Team captain access required")


@router.post("", response_model=TeamSecretResponse, status_code=201)
async def create_team(payload: TeamCreateRequest, user: User = Depends(require_capability("can_change_roster")), session: AsyncSession = Depends(get_session)) -> TeamSecretResponse:
    locked_user = await session.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if locked_user is None or locked_user.team_id is not None:
        raise HTTPException(status_code=409, detail="You already belong to a team")
    await session.execute(select(func.pg_advisory_xact_lock(ADVISORY_LOCK_KEY)))
    if int(await session.scalar(select(func.count(Team.id))) or 0) >= await _max_teams(session):
        raise HTTPException(status_code=409, detail="Maximum number of teams reached")
    secret = new_token()
    team = Team(name=payload.name, join_secret_hash=hash_password(secret), captain_id=user.id)
    session.add(team)
    try:
        await session.flush()
        locked_user.team_id = team.id
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Team name already taken") from None
    await session.refresh(team)
    return TeamSecretResponse(team=await _response(session, team), join_secret=secret)


@router.post("/join", response_model=TeamResponse)
async def join_team(payload: TeamJoinRequest, request: Request, user: User = Depends(require_capability("can_change_roster")), session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)) -> TeamResponse:
    await _limit(redis, f"rate:join:ip:{get_client_ip(request)}", settings.join_ip_limit)
    await _limit(redis, f"rate:join:user:{user.id}", settings.join_user_limit)
    locked_user = await session.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if locked_user is None or locked_user.team_id is not None:
        raise HTTPException(status_code=409, detail="You already belong to a team")
    team = await session.scalar(select(Team).where(func.lower(Team.name) == payload.name.casefold()).with_for_update())
    valid = team is not None and not team.is_banned and verify_password(team.join_secret_hash if team else DUMMY_PASSWORD_HASH, payload.secret)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid team name or join secret")
    count = await session.scalar(select(func.count(User.id)).where(User.team_id == team.id))
    if int(count or 0) >= await _team_size(session):
        raise HTTPException(status_code=409, detail="Team is full")
    locked_user.team_id = team.id
    await session.commit()
    return await _response(session, team)


@router.post("/leave", status_code=204, response_model=None)
async def leave_team(user: User = Depends(require_capability("can_change_roster")), session: AsyncSession = Depends(get_session)) -> None:
    locked_user = await session.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if locked_user is None or locked_user.team_id is None:
        raise HTTPException(status_code=409, detail="You are not in a team")
    team = await _team_or_404(session, locked_user.team_id, lock=True)
    count = int(await session.scalar(select(func.count(User.id)).where(User.team_id == team.id)) or 0)
    if team.captain_id == locked_user.id and count > 1:
        raise HTTPException(status_code=409, detail="Transfer captaincy before leaving")
    locked_user.team_id = None
    if count == 1:
        await session.delete(team)
    await session.commit()


@router.get("/me", response_model=TeamResponse | None)
async def my_team(user: User = Depends(require_user), session: AsyncSession = Depends(get_session)) -> TeamResponse | None:
    if user.team_id is None:
        return None
    return await _response(session, await _team_or_404(session, user.team_id))


@router.get("/me/score", response_model=TeamScoreResponse)
async def my_score(
    user: User = Depends(require_user), session: AsyncSession = Depends(get_session)
) -> TeamScoreResponse:
    if user.team_id is None:
        raise HTTPException(status_code=403, detail="You must be in a team to view your score")
    score = await team_score(session, user.team_id)
    rows = (
        await session.execute(
            select(Solve, Challenge)
            .join(Challenge, Challenge.id == Solve.challenge_id)
            .where(Solve.team_id == user.team_id)
            .order_by(Solve.created_at, Solve.id)
        )
    ).all()
    counts = dict(
        (challenge_id, int(count))
        for challenge_id, count in (
            await session.execute(select(Solve.challenge_id, func.count(Solve.id)).group_by(Solve.challenge_id))
        ).all()
    )
    return TeamScoreResponse(
        score=score,
        solved_challenges=[
            SolvedChallengeResponse(
                id=challenge.id,
                title=challenge.title,
                current_value=current_value(challenge, counts[solve.challenge_id]),
            )
            for solve, challenge in rows
        ],
    )


@router.get("", response_model=list[TeamSummary])
async def list_teams(session: AsyncSession = Depends(get_session)) -> list[TeamSummary]:
    teams = (await session.scalars(select(Team).where(~Team.is_hidden, ~Team.is_banned).order_by(Team.name))).all()
    return [await _public_summary(session, team) for team in teams]


@router.get("/admin", response_model=list[TeamResponse])
@router.get("/admin/all", response_model=list[TeamResponse])
async def admin_list_teams(_admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> list[TeamResponse]:
    teams = (await session.scalars(select(Team).order_by(Team.created_at))).all()
    return [await _response(session, team) for team in teams]


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(team_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> TeamResponse:
    team = await _team_or_404(session, team_id)
    if team.is_hidden or team.is_banned:
        raise HTTPException(status_code=404, detail="Team not found")
    return await _response(session, team)


@router.post("/{team_id}/kick", status_code=204, response_model=None)
async def kick_member(team_id: uuid.UUID, payload: UserTargetRequest, user: User = Depends(require_capability("can_change_roster")), session: AsyncSession = Depends(get_session)) -> None:
    target = await session.scalar(select(User).where(User.id == payload.user_id).with_for_update())
    team = await _team_or_404(session, team_id, lock=True)
    _captain_only(team, user)
    if not target or target.team_id != team.id or target.id == team.captain_id:
        raise HTTPException(status_code=404, detail="Team member not found")
    target.team_id = None
    await session.commit()


@router.post("/{team_id}/rotate-secret", response_model=TeamSecretResponse)
async def rotate_secret(team_id: uuid.UUID, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)) -> TeamSecretResponse:
    team = await _team_or_404(session, team_id, lock=True)
    _captain_only(team, user)
    secret = new_token()
    team.join_secret_hash = hash_password(secret)
    await session.commit()
    return TeamSecretResponse(team=await _response(session, team), join_secret=secret)


@router.patch("/{team_id}/rename", response_model=TeamResponse)
async def rename_team(team_id: uuid.UUID, payload: TeamRenameRequest, user: User = Depends(require_capability("can_change_roster")), session: AsyncSession = Depends(get_session)) -> TeamResponse:
    team = await _team_or_404(session, team_id, lock=True)
    _captain_only(team, user)
    team.name = payload.name
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Team name already taken") from None
    return await _response(session, team)


@router.post("/{team_id}/transfer-captain", response_model=TeamResponse)
async def transfer_captain(team_id: uuid.UUID, payload: UserTargetRequest, user: User = Depends(require_capability("can_change_roster")), session: AsyncSession = Depends(get_session)) -> TeamResponse:
    target = await session.scalar(select(User).where(User.id == payload.user_id).with_for_update())
    team = await _team_or_404(session, team_id, lock=True)
    _captain_only(team, user)
    if not target or target.team_id != team.id:
        raise HTTPException(status_code=404, detail="Team member not found")
    team.captain_id = target.id
    await session.commit()
    return await _response(session, team)


@router.patch("/admin/{team_id}", response_model=TeamResponse)
async def admin_edit_team(team_id: uuid.UUID, payload: AdminTeamEditRequest, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> TeamResponse:
    team = await _team_or_404(session, team_id, lock=True)
    if payload.name is not None:
        team.name = payload.name
    if payload.is_banned is not None:
        team.is_banned = payload.is_banned
    if payload.is_hidden is not None:
        team.is_hidden = payload.is_hidden
    session.add(AuditLog(actor_id=admin.id, action="team_edited", target=f"team:{team.id}", meta=payload.model_dump(exclude_none=True)))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Team name already taken") from None
    return await _response(session, team)


async def _admin_flag(team_id: uuid.UUID, field: str, admin: User, session: AsyncSession) -> TeamResponse:
    team = await _team_or_404(session, team_id, lock=True)
    setattr(team, field, True)
    session.add(AuditLog(actor_id=admin.id, action=f"team_{field[3:]}", target=f"team:{team.id}", meta={}))
    await session.commit()
    return await _response(session, team)


@router.post("/admin/{team_id}/ban", response_model=TeamResponse)
async def admin_ban_team(team_id: uuid.UUID, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> TeamResponse:
    return await _admin_flag(team_id, "is_banned", admin, session)


@router.post("/admin/{team_id}/hide", response_model=TeamResponse)
async def admin_hide_team(team_id: uuid.UUID, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> TeamResponse:
    return await _admin_flag(team_id, "is_hidden", admin, session)


@router.delete("/admin/{team_id}", status_code=204, response_model=None)
async def admin_delete_team(team_id: uuid.UUID, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> None:
    members = (await session.scalars(select(User).where(User.team_id == team_id).with_for_update())).all()
    team = await _team_or_404(session, team_id, lock=True)
    for member in members:
        member.team_id = None
    session.add(AuditLog(actor_id=admin.id, action="team_deleted", target=f"team:{team.id}", meta={}))
    await session.delete(team)
    await session.commit()


@router.post("/admin/move-user", response_model=TeamResponse | None)
async def admin_move_user(payload: AdminMoveUserRequest, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> TeamResponse | None:
    target_user = await session.scalar(select(User).where(User.id == payload.user_id).with_for_update())
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    old_team_id = target_user.team_id
    team_ids = sorted({team_id for team_id in (old_team_id, payload.team_id) if team_id}, key=str)
    locked_teams = {team_id: await _team_or_404(session, team_id, lock=True) for team_id in team_ids}
    destination = locked_teams.get(payload.team_id)
    if destination:
        count = int(await session.scalar(select(func.count(User.id)).where(User.team_id == destination.id)) or 0)
        if count >= await _team_size(session) and target_user.team_id != destination.id:
            raise HTTPException(status_code=409, detail="Team is full")
    if old_team_id and old_team_id != (destination.id if destination else None):
        old_team = locked_teams[old_team_id]
        if old_team.captain_id == target_user.id:
            old_team.captain_id = None
    target_user.team_id = destination.id if destination else None
    audit_target = destination.id if destination else old_team_id
    if audit_target:
        session.add(AuditLog(actor_id=admin.id, action="team_user_moved", target=f"team:{audit_target}", meta={"user_id": str(target_user.id)}))
    await session.commit()
    return await _response(session, destination) if destination else None


@router.post("/admin/{team_id}/replace-member", response_model=TeamResponse)
async def admin_replace_member(team_id: uuid.UUID, payload: AdminReplaceMemberRequest, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> TeamResponse:
    user_ids = sorted((payload.outgoing_user_id, payload.incoming_user_id), key=str)
    locked_users = (await session.scalars(select(User).where(User.id.in_(user_ids)).with_for_update())).all()
    users_by_id = {locked_user.id: locked_user for locked_user in locked_users}
    outgoing = users_by_id.get(payload.outgoing_user_id)
    incoming = users_by_id.get(payload.incoming_user_id)
    team = await _team_or_404(session, team_id, lock=True)
    if not outgoing or outgoing.team_id != team.id:
        raise HTTPException(status_code=404, detail="Outgoing team member not found")
    if not incoming or incoming.team_id is not None:
        raise HTTPException(status_code=409, detail="Incoming user already belongs to a team")
    outgoing.team_id = None
    incoming.team_id = team.id
    if team.captain_id == outgoing.id:
        team.captain_id = incoming.id
    session.add(AuditLog(actor_id=admin.id, action="team_member_replaced", target=f"team:{team.id}", meta={"outgoing_user_id": str(outgoing.id), "incoming_user_id": str(incoming.id)}))
    await session.commit()
    return await _response(session, team)
