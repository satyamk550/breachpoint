from __future__ import annotations
# ruff: noqa: E501, I001

import hmac
import uuid

import regex
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_capability, require_user
from app.api.v1.auth import enforce_limit
from app.api.v1.challenges import challenge_or_404, eligible
from app.core.client_ip import get_client_ip
from app.core.config import settings
from app.core.db import get_session
from app.core.redis import get_redis
from app.models.audit_log import AuditLog
from app.models.challenge import Challenge, Flag, Solve
from app.models.scoring import Award, ScoreEvent, Submission
from app.models.team import Team
from app.models.user import User
from app.schemas.scoring import (
    AwardResponse,
    AwardWrite,
    SolveAdjustRequest,
    SolveResponse,
    SubmissionResponse,
    SubmitRequest,
    SubmitResponse,
)
from app.services.scoring import challenge_solve_count, current_value

router = APIRouter(tags=["scoring"])


def _audit(session: AsyncSession, admin: User, action: str, target: str, meta: dict) -> None:
    session.add(AuditLog(actor_id=admin.id, action=action, target=target, meta=meta))


def _flag_matches(flag: Flag, value: str) -> bool:
    if flag.type == "static":
        left = value.casefold() if flag.case_insensitive else value
        right = flag.content.casefold() if flag.case_insensitive else flag.content
        return hmac.compare_digest(left, right)
    try:
        compiled = regex.compile(
            flag.content,
            regex.IGNORECASE if flag.case_insensitive else 0,
        )
        return compiled.fullmatch(value, timeout=0.05) is not None
    except (regex.error, TimeoutError):
        return False


async def _already_solved(session: AsyncSession, team_id: uuid.UUID, challenge_id: uuid.UUID) -> bool:
    return (
        await session.scalar(
            select(Solve.id).where(Solve.team_id == team_id, Solve.challenge_id == challenge_id)
        )
        is not None
    )


@router.post("/challenges/{challenge_id}/submit", response_model=SubmitResponse)
async def submit_flag(
    challenge_id: uuid.UUID,
    payload: SubmitRequest,
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> SubmitResponse:
    challenge = await challenge_or_404(session, challenge_id)
    if challenge.visibility != "visible":
        raise HTTPException(status_code=404, detail="Challenge not found")
    if user.team_id is None:
        raise HTTPException(status_code=403, detail="You must be in a team to submit")
    if not await eligible(session, challenge, user.team_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    await require_capability("can_submit")(user, session)
    if await _already_solved(session, user.team_id, challenge_id):
        raise HTTPException(status_code=409, detail="already solved")
    incorrect_attempts = int(
        await session.scalar(
            select(func.count(Submission.id)).where(
                Submission.team_id == user.team_id,
                Submission.challenge_id == challenge_id,
                Submission.correct.is_(False),
            )
        )
        or 0
    )
    if challenge.max_attempts is not None and incorrect_attempts >= challenge.max_attempts:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Maximum attempts reached",
                "attempts_used": incorrect_attempts,
                "attempts_remaining": 0,
            },
        )
    await enforce_limit(
        redis,
        f"rate:submit:team:{user.team_id}:challenge:{challenge_id}",
        settings.submit_attempt_limit,
        settings.submit_window_seconds,
    )
    await enforce_limit(
        redis,
        f"rate:submit:user:{user.id}",
        settings.submit_attempt_limit,
        settings.submit_window_seconds,
    )
    flags = list((await session.scalars(select(Flag).where(Flag.challenge_id == challenge_id))).all())
    correct = any(_flag_matches(flag, payload.value) for flag in flags)
    remaining = (
        None
        if challenge.max_attempts is None
        else max(0, challenge.max_attempts - incorrect_attempts - (0 if correct else 1))
    )
    ip = get_client_ip(request)
    if not correct:
        session.add(
            Submission(
                team_id=user.team_id,
                user_id=user.id,
                challenge_id=challenge_id,
                correct=False,
                provided_value=payload.value[:200],
                ip=ip,
            )
        )
        await session.commit()
        return SubmitResponse(correct=False, attempts_remaining=remaining)

    locked_challenge = await session.scalar(
        select(Challenge).where(Challenge.id == challenge_id).with_for_update()
    )
    if locked_challenge is None or await _already_solved(session, user.team_id, challenge_id):
        await session.rollback()
        raise HTTPException(status_code=409, detail="already solved")
    solve_count = await challenge_solve_count(session, challenge_id) + 1
    session.add(
        Solve(
            team_id=user.team_id,
            user_id=user.id,
            challenge_id=challenge_id,
            is_first_blood=solve_count == 1,
        )
    )
    session.add(
        Submission(
            team_id=user.team_id,
            user_id=user.id,
            challenge_id=challenge_id,
            correct=True,
            provided_value=None,
            ip=ip,
        )
    )
    session.add(
        ScoreEvent(
            team_id=user.team_id,
            kind="solve",
            challenge_id=challenge_id,
            delta=current_value(locked_challenge, solve_count),
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="already solved") from None
    return SubmitResponse(correct=True, attempts_remaining=remaining)


@router.post("/admin/awards", response_model=AwardResponse, status_code=201)
async def create_award(
    payload: AwardWrite,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Award:
    if await session.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    award = Award(created_by=admin.id, **payload.model_dump())
    session.add(award)
    await session.flush()
    session.add(ScoreEvent(team_id=award.team_id, kind="award", delta=award.value))
    _audit(session, admin, "award_created", f"award:{award.id}", {"team_id": str(award.team_id), "value": award.value})
    await session.commit()
    await session.refresh(award)
    return award


@router.delete("/admin/awards/{award_id}", status_code=204, response_model=None)
async def delete_award(
    award_id: uuid.UUID,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    award = await session.get(Award, award_id)
    if award is None:
        raise HTTPException(status_code=404, detail="Award not found")
    session.add(ScoreEvent(team_id=award.team_id, kind="award", delta=-award.value))
    _audit(session, admin, "award_deleted", f"award:{award.id}", {"team_id": str(award.team_id)})
    await session.delete(award)
    await session.commit()
    return Response(status_code=204)


@router.get("/admin/submissions", response_model=list[SubmissionResponse])
async def list_submissions(
    team_id: uuid.UUID | None = None,
    challenge_id: uuid.UUID | None = None,
    correct: bool | None = None,
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[Submission]:
    query = select(Submission).order_by(Submission.created_at, Submission.id)
    if team_id is not None:
        query = query.where(Submission.team_id == team_id)
    if challenge_id is not None:
        query = query.where(Submission.challenge_id == challenge_id)
    if correct is not None:
        query = query.where(Submission.correct.is_(correct))
    return list((await session.scalars(query)).all())


@router.get("/admin/solves", response_model=list[SolveResponse])
async def list_solves(
    _admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> list[Solve]:
    return list((await session.scalars(select(Solve).order_by(Solve.created_at, Solve.id))).all())


@router.post("/admin/solves/{solve_id}/adjust", response_model=None, status_code=204)
async def adjust_solve(
    solve_id: uuid.UUID,
    payload: SolveAdjustRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    solve = await session.scalar(select(Solve).where(Solve.id == solve_id).with_for_update())
    if solve is None:
        raise HTTPException(status_code=404, detail="Solve not found")
    challenge = await session.scalar(select(Challenge).where(Challenge.id == solve.challenge_id).with_for_update())
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    count = await challenge_solve_count(session, challenge.id)
    session.add(
        ScoreEvent(
            team_id=solve.team_id,
            kind="adjustment",
            challenge_id=solve.challenge_id,
            delta=-current_value(challenge, count),
        )
    )
    _audit(session, admin, "solve_adjusted", f"solve:{solve.id}", {"reason": payload.reason})
    await session.delete(solve)
    await session.commit()
