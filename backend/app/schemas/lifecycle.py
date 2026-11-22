from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

StateOverride = Literal["none", "live", "paused", "ended"]


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value


class LifecycleTimesRequest(BaseModel):
    start: datetime | None = None
    end: datetime | None = None

    _normalize_start = field_validator("start")(normalize_datetime)
    _normalize_end = field_validator("end")(normalize_datetime)


class LifecycleStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["draft_upcoming", "live", "paused", "ended"]
    capabilities: dict[str, bool]
    server_time: datetime
    start: datetime | None
    end: datetime | None
    freeze_enabled: bool
    freeze_time: datetime | None
