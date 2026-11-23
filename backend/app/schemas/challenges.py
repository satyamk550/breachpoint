import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def nonblank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("value is required")
    return value


class CategoryWrite(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    sort_order: int = Field(default=0)
    _name = field_validator("name")(nonblank)


class CategoryResponse(CategoryWrite):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class ChallengeWrite(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description_md: str = Field(min_length=1, max_length=20000)
    category_id: uuid.UUID
    points: int = Field(default=0, ge=0)
    scoring_mode: Literal["static", "dynamic"] = "static"
    initial: int = 0
    minimum: int = 0
    decay: float = Field(default=1, gt=0)
    function: Literal["linear", "logarithmic"] = "linear"
    visibility: Literal["draft", "visible", "hidden"] = "draft"
    max_attempts: int | None = Field(default=None, ge=1)
    connection_info: str | None = Field(default=None, max_length=5000)
    author: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list, max_length=50)
    prerequisites: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @field_validator("title", "description_md")
    @classmethod
    def trim_required(cls, value: str) -> str:
        return nonblank(value)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        return [nonblank(value) for value in values]

    @model_validator(mode="after")
    def validate_dynamic(self):
        if self.scoring_mode == "dynamic" and self.initial < self.minimum:
            raise ValueError("initial must be greater than or equal to minimum for dynamic scoring")
        if len(set(self.prerequisites)) != len(self.prerequisites):
            raise ValueError("prerequisites must be unique")
        return self


class ChallengePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description_md: str | None = Field(default=None, min_length=1, max_length=20000)
    category_id: uuid.UUID | None = None
    points: int | None = Field(default=None, ge=0)
    scoring_mode: Literal["static", "dynamic"] | None = None
    initial: int | None = None
    minimum: int | None = None
    decay: float | None = Field(default=None, gt=0)
    function: Literal["linear", "logarithmic"] | None = None
    visibility: Literal["draft", "visible", "hidden"] | None = None
    max_attempts: int | None = Field(default=None, ge=1)
    connection_info: str | None = Field(default=None, max_length=5000)
    author: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = Field(default=None, max_length=50)
    prerequisites: list[uuid.UUID] | None = Field(default=None, max_length=50)

    @field_validator("title", "description_md")
    @classmethod
    def trim_patch(cls, value: str | None) -> str | None:
        return nonblank(value) if value is not None else None


class VisibilityChange(BaseModel):
    visibility: Literal["draft", "visible", "hidden"]
    challenge_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class FlagWrite(BaseModel):
    type: Literal["static", "regex"]
    content: str = Field(min_length=1, max_length=500)
    case_insensitive: bool = False

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("flag content is required")
        return value

    @model_validator(mode="after")
    def validate_regex(self):
        if self.type == "regex":
            try:
                re.compile(self.content)
            except re.error as exc:
                raise ValueError(f"invalid regex flag: {exc}") from exc
        return self


class FlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: Literal["static", "regex"]
    case_insensitive: bool


class ChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    description_md: str
    category_id: uuid.UUID
    points: int
    scoring_mode: str
    initial: int
    minimum: int
    decay: float
    function: str
    visibility: str
    max_attempts: int | None
    connection_info: str | None
    author: str | None
    created_at: datetime
    tags: list[str] = Field(default_factory=list)
    prerequisites: list[uuid.UUID] = Field(default_factory=list)
    solve_count: int = 0
    solved_by_my_team: bool = False


class PlayerChallengeResponse(BaseModel):
    id: uuid.UUID
    title: str
    description_md: str
    category_id: uuid.UUID
    points: int
    connection_info: str | None
    tags: list[str] = Field(default_factory=list)
    solve_count: int
    solved_by_my_team: bool


class ChallengeGroup(BaseModel):
    category_id: uuid.UUID
    category_name: str
    sort_order: int
    challenges: list[PlayerChallengeResponse]
