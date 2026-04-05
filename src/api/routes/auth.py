"""Authentication endpoints for the dashboard UI (Task 9.1)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.api.schemas.dashboard import AuthUserResponse

router = APIRouter(tags=["auth"])


@router.get(
    "/auth/me",
    response_model=AuthUserResponse,
    summary="Get current user",
    description=(
        "Return the currently authenticated user based on SSO proxy headers. "
        "Falls back to developer defaults when headers are absent (dev mode)."
    ),
)
async def get_current_user(request: Request) -> AuthUserResponse:
    """Extract user identity from SSO proxy headers.

    Headers expected from an authenticating reverse proxy:
    - X-Forwarded-User: username
    - X-Forwarded-Email: email address
    - X-Forwarded-Role: role (admin, editor, viewer)

    In development mode (no proxy), sensible defaults are returned.
    """
    username = request.headers.get("X-Forwarded-User", "developer")
    email = request.headers.get("X-Forwarded-Email", "dev@local")
    role = request.headers.get("X-Forwarded-Role", "admin")

    return AuthUserResponse(
        username=username,
        email=email,
        role=role,
    )
