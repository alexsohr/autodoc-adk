"""Sanitized ADK DatabaseSessionService for PostgreSQL compatibility."""

from __future__ import annotations

import logging
from typing import Any

from google.adk.events.event import Event
from google.adk.sessions import DatabaseSessionService
from google.adk.sessions.session import Session

logger = logging.getLogger(__name__)


def _strip_null_bytes(obj: Any) -> Any:
    """Recursively strip null bytes from all strings in a nested structure."""
    if isinstance(obj, str):
        return obj.replace("\x00", "")
    if isinstance(obj, dict):
        return {k: _strip_null_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_null_bytes(item) for item in obj]
    return obj


class SanitizedDatabaseSessionService(DatabaseSessionService):
    """DatabaseSessionService that strips null bytes before PostgreSQL insertion.

    PostgreSQL text/jsonb columns reject ``\\u0000``.  LLM output occasionally
    contains null bytes, causing ``asyncpg.UntranslatableCharacterError`` when
    ADK persists agent events.  This subclass sanitizes event data before it
    reaches the database.
    """

    async def append_event(self, session: Session, event: Event) -> Event:
        data = event.model_dump(mode="json")
        sanitized = _strip_null_bytes(data)
        if sanitized != data:
            logger.warning(
                "Stripped null bytes from event %s in session %s",
                event.id,
                session.id,
            )
            event = Event.model_validate(sanitized)
        return await super().append_event(session, event)
