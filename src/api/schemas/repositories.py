from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegisterRepositoryRequest(BaseModel):
    url: str
    provider: Literal["github", "bitbucket"]
    branch_mappings: dict[str, str] = Field(..., min_length=1)
    public_branch: str
    access_token: str | None = None

    @model_validator(mode="after")
    def _validate_public_branch_in_mappings(self) -> RegisterRepositoryRequest:
        if self.public_branch not in self.branch_mappings:
            msg = f"public_branch '{self.public_branch}' must be a key in branch_mappings"
            raise ValueError(msg)
        return self


class UpdateRepositoryRequest(BaseModel):
    branch_mappings: dict[str, str] | None = None
    public_branch: str | None = None
    access_token: str | None = None


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    provider: str
    org: str
    name: str
    branch_mappings: dict[str, str]
    public_branch: str
    created_at: datetime
    updated_at: datetime


class PaginatedRepositoryResponse(BaseModel):
    items: list[RepositoryResponse]
    next_cursor: str | None = None
    limit: int
