import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubmitRequest(BaseModel):
    value: str = Field(min_length=1, max_length=500)

    @field_validator("value")
    @classmethod
    def trim_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("submission value is required")
        return value


class SubmitResponse(BaseModel):
    correct: bool
    attempts_remaining: int | None


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    challenge_id: uuid.UUID
    correct: bool
    provided_value: str | None
    created_at: datetime
    ip: str


class AwardWrite(BaseModel):
    team_id: uuid.UUID
    name: str = Field(min_length=1, max_length=128)
    value: int
    reason: str = Field(min_length=1, max_length=5000)

    @field_validator("name", "reason")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value is required")
        return value

    @field_validator("value")
    @classmethod
    def nonzero_value(cls, value: int) -> int:
        if value == 0:
            raise ValueError("award value cannot be zero")
        return value


class AwardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    value: int
    reason: str
    created_by: uuid.UUID
    created_at: datetime


class SolveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    challenge_id: uuid.UUID
    created_at: datetime
    is_first_blood: bool


class SolveAdjustRequest(BaseModel):
    action: Literal["delete"]
    reason: str = Field(min_length=1, max_length=5000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason is required")
        return value


class SolvedChallengeResponse(BaseModel):
    id: uuid.UUID
    title: str
    current_value: int


class TeamScoreResponse(BaseModel):
    score: int
    solved_challenges: list[SolvedChallengeResponse]
