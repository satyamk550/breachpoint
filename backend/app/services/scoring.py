from __future__ import annotations
# ruff: noqa: E501, I001

import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge, Hint, HintUnlock, Solve
from app.models.scoring import Award


def current_value(challenge: Challenge, solve_count: int) -> int:
    """Return the integer value of a challenge after the given solve count."""
    solves = max(1, solve_count)
    if challenge.scoring_mode == "static":
        return challenge.points
    if challenge.function == "linear":
        value = challenge.initial - challenge.decay * (solves - 1)
        return max(challenge.minimum, math.floor(value))
    value = ((challenge.minimum - challenge.initial) / challenge.decay**2) * (solves - 1) ** 2
    return max(challenge.minimum, math.ceil(value + challenge.initial))


async def challenge_solve_count(session: AsyncSession, challenge_id: uuid.UUID) -> int:
    return int(
        await session.scalar(select(func.count(Solve.id)).where(Solve.challenge_id == challenge_id))
        or 0
    )


async def team_score(session: AsyncSession, team_id: uuid.UUID) -> int:
    solves = (
        await session.execute(
            select(Solve, Challenge)
            .join(Challenge, Challenge.id == Solve.challenge_id)
            .where(Solve.team_id == team_id)
        )
    ).all()
    counts = dict(
        (
            challenge_id,
            int(count),
        )
        for challenge_id, count in (
            await session.execute(
                select(Solve.challenge_id, func.count(Solve.id))
                .group_by(Solve.challenge_id)
            )
        ).all()
    )
    solve_points = sum(current_value(challenge, counts[solve.challenge_id]) for solve, challenge in solves)
    hint_cost = int(
        await session.scalar(
            select(func.coalesce(func.sum(Hint.cost), 0))
            .join(HintUnlock, HintUnlock.hint_id == Hint.id)
            .where(HintUnlock.team_id == team_id)
        )
        or 0
    )
    award_value = int(
        await session.scalar(select(func.coalesce(func.sum(Award.value), 0)).where(Award.team_id == team_id))
        or 0
    )
    return max(0, solve_points - hint_cost + award_value)
