from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str


class PaginatedResponse(BaseModel):
    """Wrapper for paginated list responses."""

    items: list = Field(default_factory=list)
    next_cursor: str | None = None
    limit: int = 20
