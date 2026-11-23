import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def clean_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Team name is required")
    return value


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    _clean_name = field_validator("name")(clean_name)


class TeamJoinRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    secret: str = Field(min_length=1, max_length=256)
    _clean_name = field_validator("name")(clean_name)


class TeamRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    _clean_name = field_validator("name")(clean_name)


class UserTargetRequest(BaseModel):
    user_id: uuid.UUID


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    role: str


class TeamSummary(BaseModel):
    id: uuid.UUID
    name: str
    member_count: int


class TeamResponse(TeamSummary):
    captain_id: uuid.UUID | None
    is_banned: bool = False
    is_hidden: bool = False
    created_at: datetime
    members: list[TeamMemberResponse] = Field(default_factory=list)


class TeamSecretResponse(BaseModel):
    team: TeamResponse
    join_secret: str


class AdminTeamEditRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_banned: bool | None = None
    is_hidden: bool | None = None
    _clean_name = field_validator("name")(
        lambda value: clean_name(value) if value is not None else value
    )


class AdminMoveUserRequest(BaseModel):
    user_id: uuid.UUID
    team_id: uuid.UUID | None


class AdminReplaceMemberRequest(BaseModel):
    outgoing_user_id: uuid.UUID
    incoming_user_id: uuid.UUID
