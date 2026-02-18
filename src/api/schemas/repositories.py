from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegisterRepositoryRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "url": "https://github.com/acme-corp/backend-api",
                    "provider": "github",
                    "branch_mappings": {
                        "main": "production",
                        "develop": "staging",
                    },
                    "public_branch": "main",
                    "access_token": "ghp_a1b2c3d4e5f6g7h8i9j0kLmNoPqRsTuVwXyZ",
                },
                {
                    "url": "https://bitbucket.org/acme-corp/frontend-app",
                    "provider": "bitbucket",
                    "branch_mappings": {
                        "master": "latest",
                    },
                    "public_branch": "master",
                    "access_token": None,
                },
            ],
        },
    )

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
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "branch_mappings": {
                        "main": "production",
                        "develop": "staging",
                        "release/v2": "v2-preview",
                    },
                    "public_branch": "main",
                    "access_token": None,
                },
                {
                    "branch_mappings": None,
                    "public_branch": None,
                    "access_token": "ghp_NewRotatedToken9x8y7z6w5v4u3t2s1r0q",
                },
            ],
        },
    )

    branch_mappings: dict[str, str] | None = None
    public_branch: str | None = None
    access_token: str | None = None


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "url": "https://github.com/acme-corp/backend-api",
                "provider": "github",
                "org": "acme-corp",
                "name": "backend-api",
                "branch_mappings": {
                    "main": "production",
                    "develop": "staging",
                },
                "public_branch": "main",
                "created_at": "2026-01-15T10:30:00Z",
                "updated_at": "2026-02-10T14:22:00Z",
            },
        },
    )

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
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "url": "https://github.com/acme-corp/backend-api",
                        "provider": "github",
                        "org": "acme-corp",
                        "name": "backend-api",
                        "branch_mappings": {
                            "main": "production",
                            "develop": "staging",
                        },
                        "public_branch": "main",
                        "created_at": "2026-01-15T10:30:00Z",
                        "updated_at": "2026-02-10T14:22:00Z",
                    },
                ],
                "next_cursor": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "limit": 20,
            },
        },
    )

    items: list[RepositoryResponse]
    next_cursor: str | None = None
    limit: int
