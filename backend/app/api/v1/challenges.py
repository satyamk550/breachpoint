from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_capability
from app.core.db import get_session
from app.models.audit_log import AuditLog
from app.models.challenge import Category, Challenge, ChallengePrerequisite, Flag, Solve, Tag
from app.models.user import User
from app.schemas.challenges import (
    CategoryResponse,
    CategoryWrite,
    ChallengeGroup,
    ChallengePatch,
    ChallengeResponse,
    ChallengeWrite,
    FlagWrite,
    PlayerChallengeResponse,
    VisibilityChange,
)

router = APIRouter(tags=["challenges"])


async def audit(
    session: AsyncSession,
    admin: User,
    action: str,
    challenge_id: uuid.UUID | None = None,
    flag_id: uuid.UUID | None = None,
) -> None:
    meta = {
        key: str(value)
        for key, value in (("challenge_id", challenge_id), ("flag_id", flag_id))
        if value is not None
    }
    session.add(
        AuditLog(
            actor_id=admin.id,
            action=action,
            target=f"challenge:{challenge_id}"
            if challenge_id
            else (f"flag:{flag_id}" if flag_id else action),
            meta=meta,
        )
    )


async def challenge_or_404(session: AsyncSession, challenge_id: uuid.UUID) -> Challenge:
    challenge = await session.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge


async def category_or_404(session: AsyncSession, category_id: uuid.UUID) -> Category:
    category = await session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


async def ensure_category(session: AsyncSession, category_id: uuid.UUID) -> None:
    await category_or_404(session, category_id)


async def ensure_no_cycle(
    session: AsyncSession, challenge_id: uuid.UUID, required_ids: list[uuid.UUID]
) -> None:
    if challenge_id in required_ids:
        raise HTTPException(status_code=422, detail="A challenge cannot require itself")
    rows = (await session.scalars(select(ChallengePrerequisite))).all()
    graph: dict[uuid.UUID, set[uuid.UUID]] = {}
    for row in rows:
        graph.setdefault(row.challenge_id, set()).add(row.requires_challenge_id)
    graph[challenge_id] = set(required_ids)
    visiting: set[uuid.UUID] = set()
    visited: set[uuid.UUID] = set()

    def visit(node: uuid.UUID) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in graph.get(node, set())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    if any(visit(node) for node in graph):
        raise HTTPException(
            status_code=422, detail="Challenge prerequisites cannot contain a cycle"
        )


async def ensure_prerequisites_exist(session: AsyncSession, required_ids: list[uuid.UUID]) -> None:
    if not required_ids:
        return
    found = set(
        (await session.scalars(select(Challenge.id).where(Challenge.id.in_(required_ids)))).all()
    )
    if found != set(required_ids):
        raise HTTPException(
            status_code=422, detail="Every prerequisite must reference an existing challenge"
        )


async def replace_tags_and_prereqs(
    session: AsyncSession, challenge_id: uuid.UUID, tags: list[str], prerequisites: list[uuid.UUID]
) -> None:
    await ensure_prerequisites_exist(session, prerequisites)
    await ensure_no_cycle(session, challenge_id, prerequisites)
    existing = (await session.scalars(select(Tag).where(Tag.challenge_id == challenge_id))).all()
    for tag in existing:
        await session.delete(tag)
    await session.execute(
        delete(ChallengePrerequisite).where(ChallengePrerequisite.challenge_id == challenge_id)
    )
    session.add_all([Tag(challenge_id=challenge_id, value=value) for value in dict.fromkeys(tags)])
    session.add_all(
        [
            ChallengePrerequisite(challenge_id=challenge_id, requires_challenge_id=value)
            for value in prerequisites
        ]
    )


async def admin_challenge_response(
    session: AsyncSession, challenge: Challenge
) -> ChallengeResponse:
    tags = list(
        (await session.scalars(select(Tag.value).where(Tag.challenge_id == challenge.id))).all()
    )
    prereqs = list(
        (
            await session.scalars(
                select(ChallengePrerequisite.requires_challenge_id).where(
                    ChallengePrerequisite.challenge_id == challenge.id
                )
            )
        ).all()
    )
    count = int(
        await session.scalar(select(func.count(Solve.id)).where(Solve.challenge_id == challenge.id))
        or 0
    )
    return ChallengeResponse.model_validate(challenge).model_copy(
        update={"tags": tags, "prerequisites": prereqs, "solve_count": count}
    )


async def player_challenge_response(
    session: AsyncSession, challenge: Challenge, team_id: uuid.UUID
) -> PlayerChallengeResponse:
    tags = list(
        (await session.scalars(select(Tag.value).where(Tag.challenge_id == challenge.id))).all()
    )
    count = int(
        await session.scalar(select(func.count(Solve.id)).where(Solve.challenge_id == challenge.id))
        or 0
    )
    solved = await session.scalar(
        select(Solve.id).where(Solve.challenge_id == challenge.id, Solve.team_id == team_id)
    )
    return PlayerChallengeResponse(
        id=challenge.id,
        title=challenge.title,
        description_md=challenge.description_md,
        category_id=challenge.category_id,
        points=challenge.points,
        connection_info=challenge.connection_info,
        tags=tags,
        solve_count=count,
        solved_by_my_team=solved is not None,
    )


async def eligible(session: AsyncSession, challenge: Challenge, team_id: uuid.UUID) -> bool:
    if challenge.visibility != "visible":
        return False
    required = list(
        (
            await session.scalars(
                select(ChallengePrerequisite.requires_challenge_id).where(
                    ChallengePrerequisite.challenge_id == challenge.id
                )
            )
        ).all()
    )
    if not required:
        return True
    solved = set(
        (
            await session.scalars(
                select(Solve.challenge_id).where(
                    Solve.team_id == team_id, Solve.challenge_id.in_(required)
                )
            )
        ).all()
    )
    return set(required) <= solved


@router.get("/challenges", response_model=list[ChallengeGroup])
async def list_player_challenges(
    user: User = Depends(require_capability("can_view_challenges")),
    session: AsyncSession = Depends(get_session),
) -> list[ChallengeGroup]:
    if user.team_id is None:
        raise HTTPException(status_code=403, detail="You must be in a team to view challenges")
    categories = (
        await session.scalars(select(Category).order_by(Category.sort_order, Category.name))
    ).all()
    challenges = (await session.scalars(select(Challenge).order_by(Challenge.created_at))).all()
    by_category: dict[uuid.UUID, list[PlayerChallengeResponse]] = {
        category.id: [] for category in categories
    }
    for challenge in challenges:
        if challenge.category_id in by_category and await eligible(
            session, challenge, user.team_id
        ):
            by_category[challenge.category_id].append(
                await player_challenge_response(session, challenge, user.team_id)
            )
    return [
        ChallengeGroup(
            category_id=c.id,
            category_name=c.name,
            sort_order=c.sort_order,
            challenges=by_category[c.id],
        )
        for c in categories
        if by_category[c.id]
    ]


@router.get("/challenges/{challenge_id}", response_model=PlayerChallengeResponse)
async def get_player_challenge(
    challenge_id: uuid.UUID,
    user: User = Depends(require_capability("can_view_challenges")),
    session: AsyncSession = Depends(get_session),
) -> PlayerChallengeResponse:
    if user.team_id is None:
        raise HTTPException(status_code=403, detail="You must be in a team to view challenges")
    challenge = await challenge_or_404(session, challenge_id)
    if not await eligible(session, challenge, user.team_id):
        raise HTTPException(status_code=404, detail="Challenge not found")
    return await player_challenge_response(session, challenge, user.team_id)


@router.get("/admin/categories", response_model=list[CategoryResponse])
async def admin_list_categories(
    _admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> list[Category]:
    return list(
        (await session.scalars(select(Category).order_by(Category.sort_order, Category.name))).all()
    )


@router.post("/admin/categories", response_model=CategoryResponse, status_code=201)
async def admin_create_category(
    payload: CategoryWrite,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Category:
    category = Category(**payload.model_dump())
    session.add(category)
    try:
        await session.flush()
        await audit(session, admin, "category_created")
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Category name already taken") from None
    await session.refresh(category)
    return category


@router.patch("/admin/categories/{category_id}", response_model=CategoryResponse)
async def admin_update_category(
    category_id: uuid.UUID,
    payload: CategoryWrite,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Category:
    category = await category_or_404(session, category_id)
    category.name = payload.name
    category.sort_order = payload.sort_order
    try:
        await audit(session, admin, "category_updated")
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Category name already taken") from None
    return category


@router.delete("/admin/categories/{category_id}", status_code=204, response_model=None)
async def admin_delete_category(
    category_id: uuid.UUID,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    category = await category_or_404(session, category_id)
    if await session.scalar(select(Challenge.id).where(Challenge.category_id == category_id)):
        raise HTTPException(status_code=409, detail="Category has challenges")
    await session.delete(category)
    await audit(session, admin, "category_deleted")
    await session.commit()


@router.get("/admin/challenges", response_model=list[ChallengeResponse])
async def admin_list_challenges(
    _admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> list[ChallengeResponse]:
    return [
        await admin_challenge_response(session, item)
        for item in (await session.scalars(select(Challenge).order_by(Challenge.created_at))).all()
    ]


@router.get("/admin/challenges/{challenge_id}", response_model=ChallengeResponse)
async def admin_get_challenge(
    challenge_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ChallengeResponse:
    return await admin_challenge_response(session, await challenge_or_404(session, challenge_id))


@router.post("/admin/challenges", response_model=ChallengeResponse, status_code=201)
async def admin_create_challenge(
    payload: ChallengeWrite,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ChallengeResponse:
    await ensure_category(session, payload.category_id)
    challenge = Challenge(**payload.model_dump(exclude={"tags", "prerequisites"}))
    session.add(challenge)
    await session.flush()
    await replace_tags_and_prereqs(session, challenge.id, payload.tags, payload.prerequisites)
    await audit(session, admin, "challenge_created", challenge.id)
    await session.commit()
    await session.refresh(challenge)
    return await admin_challenge_response(session, challenge)


@router.patch("/admin/challenges/{challenge_id}", response_model=ChallengeResponse)
async def admin_update_challenge(
    challenge_id: uuid.UUID,
    payload: ChallengePatch,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ChallengeResponse:
    challenge = await challenge_or_404(session, challenge_id)
    values = payload.model_dump(exclude_unset=True, exclude={"tags", "prerequisites"})
    if "category_id" in values:
        await ensure_category(session, values["category_id"])
    for key, value in values.items():
        setattr(challenge, key, value)
    if payload.scoring_mode == "dynamic" or challenge.scoring_mode == "dynamic":
        if challenge.initial < challenge.minimum:
            raise HTTPException(
                status_code=422,
                detail="initial must be greater than or equal to minimum for dynamic scoring",
            )
    if payload.tags is not None or payload.prerequisites is not None:
        current_tags = (
            list(
                (
                    await session.scalars(select(Tag.value).where(Tag.challenge_id == challenge.id))
                ).all()
            )
            if payload.tags is None
            else payload.tags
        )
        current_prereqs = (
            list(
                (
                    await session.scalars(
                        select(ChallengePrerequisite.requires_challenge_id).where(
                            ChallengePrerequisite.challenge_id == challenge.id
                        )
                    )
                ).all()
            )
            if payload.prerequisites is None
            else payload.prerequisites
        )
        await replace_tags_and_prereqs(session, challenge.id, current_tags, current_prereqs)
    await audit(session, admin, "challenge_updated", challenge.id)
    await session.commit()
    return await admin_challenge_response(session, challenge)


@router.delete("/admin/challenges/{challenge_id}", status_code=204, response_model=None)
async def admin_delete_challenge(
    challenge_id: uuid.UUID,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    challenge = await challenge_or_404(session, challenge_id)
    if await session.scalar(select(Solve.id).where(Solve.challenge_id == challenge_id)):
        raise HTTPException(status_code=409, detail="Challenge has solves; hide it instead")
    await session.delete(challenge)
    await audit(session, admin, "challenge_deleted", challenge_id)
    await session.commit()


@router.post("/admin/challenges/visibility", response_model=list[ChallengeResponse])
async def admin_bulk_visibility(
    payload: VisibilityChange,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ChallengeResponse]:
    challenges = list(
        (
            await session.scalars(select(Challenge).where(Challenge.id.in_(payload.challenge_ids)))
        ).all()
    )
    if len(challenges) != len(set(payload.challenge_ids)):
        raise HTTPException(status_code=404, detail="Challenge not found")
    for challenge in challenges:
        challenge.visibility = payload.visibility
        await audit(session, admin, "challenge_visibility_changed", challenge.id)
    await session.commit()
    return [await admin_challenge_response(session, item) for item in challenges]


@router.post(
    "/admin/challenges/{challenge_id}/clone", response_model=ChallengeResponse, status_code=201
)
async def admin_clone_challenge(
    challenge_id: uuid.UUID,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ChallengeResponse:
    source = await challenge_or_404(session, challenge_id)
    clone = Challenge(
        title=f"{source.title} (copy)",
        description_md=source.description_md,
        category_id=source.category_id,
        points=source.points,
        scoring_mode=source.scoring_mode,
        initial=source.initial,
        minimum=source.minimum,
        decay=source.decay,
        function=source.function,
        visibility="draft",
        max_attempts=source.max_attempts,
        connection_info=source.connection_info,
        author=source.author,
    )
    session.add(clone)
    await session.flush()
    source_tags = list(
        (await session.scalars(select(Tag.value).where(Tag.challenge_id == source.id))).all()
    )
    source_flags = list(
        (await session.scalars(select(Flag).where(Flag.challenge_id == source.id))).all()
    )
    session.add_all([Tag(challenge_id=clone.id, value=value) for value in source_tags])
    session.add_all(
        [
            Flag(
                challenge_id=clone.id,
                type=flag.type,
                content=flag.content,
                case_insensitive=flag.case_insensitive,
            )
            for flag in source_flags
        ]
    )
    await audit(session, admin, "challenge_cloned", clone.id)
    await session.commit()
    return await admin_challenge_response(session, clone)


@router.get("/admin/challenges/{challenge_id}/flags", response_model=list[dict])
async def admin_list_flags(
    challenge_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    await challenge_or_404(session, challenge_id)
    return [
        {
            "id": flag.id,
            "type": flag.type,
            "content": flag.content,
            "case_insensitive": flag.case_insensitive,
        }
        for flag in (
            await session.scalars(select(Flag).where(Flag.challenge_id == challenge_id))
        ).all()
    ]


@router.post("/admin/challenges/{challenge_id}/flags", response_model=dict, status_code=201)
async def admin_create_flag(
    challenge_id: uuid.UUID,
    payload: FlagWrite,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await challenge_or_404(session, challenge_id)
    flag = Flag(challenge_id=challenge_id, **payload.model_dump())
    session.add(flag)
    await session.flush()
    await audit(session, admin, "flag_created", challenge_id, flag.id)
    await session.commit()
    return {
        "id": flag.id,
        "type": flag.type,
        "content": flag.content,
        "case_insensitive": flag.case_insensitive,
    }


@router.patch("/admin/challenges/{challenge_id}/flags/{flag_id}", response_model=dict)
async def admin_update_flag(
    challenge_id: uuid.UUID,
    flag_id: uuid.UUID,
    payload: FlagWrite,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await challenge_or_404(session, challenge_id)
    flag = await session.scalar(
        select(Flag).where(Flag.id == flag_id, Flag.challenge_id == challenge_id)
    )
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    for key, value in payload.model_dump().items():
        setattr(flag, key, value)
    await audit(session, admin, "flag_updated", challenge_id, flag.id)
    await session.commit()
    return {
        "id": flag.id,
        "type": flag.type,
        "content": flag.content,
        "case_insensitive": flag.case_insensitive,
    }


@router.delete(
    "/admin/challenges/{challenge_id}/flags/{flag_id}", status_code=204, response_model=None
)
async def admin_delete_flag(
    challenge_id: uuid.UUID,
    flag_id: uuid.UUID,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    await challenge_or_404(session, challenge_id)
    flag = await session.scalar(
        select(Flag).where(Flag.id == flag_id, Flag.challenge_id == challenge_id)
    )
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    await session.delete(flag)
    await audit(session, admin, "flag_deleted", challenge_id, flag_id)
    await session.commit()
