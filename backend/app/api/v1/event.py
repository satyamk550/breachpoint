from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_session
from app.models.audit_log import AuditLog
from app.models.config import Config
from app.models.user import User
from app.schemas.lifecycle import EventAuditEntry, LifecycleStatus, LifecycleTimesRequest
from app.services.lifecycle import (
    get_capabilities,
    get_state,
    parse_datetime,
    read_lifecycle_config,
    utc_now,
)

router = APIRouter(prefix="/event", tags=["event"])

async def write_config(session: AsyncSession, key: str, value: str) -> None:
    config = await session.get(Config, key)
    if config is None:
        config = Config(key=key, value=value)
        session.add(config)
    else:
        config.value = value


async def status_payload(
    session: AsyncSession, clock: Callable[[], datetime] = utc_now
) -> LifecycleStatus:
    values = await read_lifecycle_config(session)
    now = clock()
    state = get_state(
        now,
        event_start=parse_datetime(values["event_start"]),
        event_end=parse_datetime(values["event_end"]),
        state_override=values["state_override"],
    )
    return LifecycleStatus(
        state=state,
        capabilities=get_capabilities(state),
        server_time=now,
        start=parse_datetime(values["event_start"]),
        end=parse_datetime(values["event_end"]),
        freeze_enabled=values["freeze_enabled"].casefold() == "true",
        freeze_time=parse_datetime(values["freeze_time"]),
    )


async def record_action(
    session: AsyncSession, actor: User, action: str, meta: dict[str, object] | None = None
) -> None:
    session.add(
        AuditLog(actor_id=actor.id, action=action, target="event", meta=meta or {})
    )


@router.get("/status", response_model=LifecycleStatus)
async def event_status(session: AsyncSession = Depends(get_session)) -> LifecycleStatus:
    return await status_payload(session)


@router.get("/admin/audit", response_model=list[EventAuditEntry])
async def event_audit(
    limit: int = Query(default=10, ge=1, le=50),
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[EventAuditEntry]:
    rows = (
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.target == "event")
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
        )
    ).all()
    return [
        EventAuditEntry(
            id=str(row.id),
            action=row.action,
            target=row.target,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.put("/admin/times", response_model=LifecycleStatus)
async def set_event_times(
    payload: LifecycleTimesRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> LifecycleStatus:
    if payload.start and payload.end and payload.end <= payload.start:
        raise HTTPException(status_code=422, detail="Event end must be after event start")
    start_value = payload.start.astimezone(UTC).isoformat() if payload.start else ""
    end_value = payload.end.astimezone(UTC).isoformat() if payload.end else ""
    await write_config(session, "event_start", start_value)
    await write_config(session, "event_end", end_value)
    await record_action(
        session,
        admin,
        "event_times_updated",
        {
            "start": payload.start.isoformat() if payload.start else None,
            "end": payload.end.isoformat() if payload.end else None,
        },
    )
    await session.commit()
    return await status_payload(session)


async def set_override(
    value: str,
    action: str,
    admin: User,
    session: AsyncSession,
) -> LifecycleStatus:
    await write_config(session, "state_override", value)
    await record_action(session, admin, action, {"state_override": value})
    await session.commit()
    return await status_payload(session)


@router.post("/admin/start", response_model=LifecycleStatus)
async def start_event(
    admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> LifecycleStatus:
    current = await status_payload(session)
    if current.state == "ended":
        raise HTTPException(
            status_code=409,
            detail="Event has already ended; update the event end time before starting it",
        )
    now = utc_now()
    await write_config(session, "event_start", now.isoformat())
    await write_config(session, "state_override", "live")
    await record_action(session, admin, "event_started", {"start": now.isoformat()})
    await session.commit()
    return await status_payload(session)


@router.post("/admin/pause", response_model=LifecycleStatus)
async def pause_event(
    admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> LifecycleStatus:
    return await set_override("paused", "event_paused", admin, session)


@router.post("/admin/resume", response_model=LifecycleStatus)
async def resume_event(
    admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> LifecycleStatus:
    return await set_override("live", "event_resumed", admin, session)


@router.post("/admin/end", response_model=LifecycleStatus)
async def end_event(
    admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> LifecycleStatus:
    return await set_override("ended", "event_ended", admin, session)


@router.post("/admin/reset", response_model=LifecycleStatus)
async def reset_event(
    admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> LifecycleStatus:
    await write_config(session, "event_start", "")
    await write_config(session, "event_end", "")
    await write_config(session, "state_override", "none")
    await record_action(session, admin, "event_reset", {"state_override": "none"})
    await session.commit()
    return await status_payload(session)
