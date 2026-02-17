from __future__ import annotations

from pydantic import BaseModel


class ScopeInfo(BaseModel):
    """Information about a documentation scope."""

    scope_path: str
    title: str | None = None
    description: str | None = None
    page_count: int = 0


class ScopesResponse(BaseModel):
    """Response for the list scopes endpoint."""

    scopes: list[ScopeInfo]
