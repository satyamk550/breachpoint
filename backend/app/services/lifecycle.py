from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import Config

LifecycleState = Literal["draft_upcoming", "live", "paused", "ended"]
StateOverride = Literal["none", "live", "paused", "ended"]
CONFIG_KEYS = {
    "event_start", "event_end", "state_override", "freeze_enabled", "freeze_time",
    "team_size", "max_teams",
}


@dataclass(frozen=True)
class Capabilities:
    can_view_challenges: bool
    can_submit: bool
    can_unlock_hints: bool
    can_change_roster: bool
    can_view_scoreboard: bool


CAPABILITIES: dict[LifecycleState, Capabilities] = {
    "draft_upcoming": Capabilities(False, False, False, True, False),
    "live": Capabilities(True, True, True, False, True),
    "paused": Capabilities(True, False, False, False, True),
    "ended": Capabilities(True, False, False, False, True),
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_state(
    now: datetime | None = None,
    *,
    event_start: datetime | None = None,
    event_end: datetime | None = None,
    state_override: StateOverride = "none",
    clock: Callable[[], datetime] = utc_now,
) -> LifecycleState:
    if state_override != "none":
        return state_override
    current = (now or clock()).astimezone(UTC)
    if event_end is not None and current >= event_end.astimezone(UTC):
        return "ended"
    if event_start is not None and current >= event_start.astimezone(UTC):
        return "live"
    return "draft_upcoming"


def get_capabilities(state: LifecycleState) -> dict[str, bool]:
    return CAPABILITIES[state].__dict__.copy()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


async def read_lifecycle_config(session: AsyncSession) -> dict[str, str]:
    rows = (await session.scalars(select(Config).where(Config.key.in_(CONFIG_KEYS)))).all()
    values = {row.key: row.value for row in rows}
    return {
        "event_start": values.get("event_start", ""),
        "event_end": values.get("event_end", ""),
        "state_override": values.get("state_override", "none"),
        "freeze_enabled": values.get("freeze_enabled", "false"),
        "freeze_time": values.get("freeze_time", ""),
    }
