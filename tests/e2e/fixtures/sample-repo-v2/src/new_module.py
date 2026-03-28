"""New module added in v2 for testing incremental detection."""

from __future__ import annotations


class EventHandler:
    """Handles events in the processing pipeline."""

    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}

    def register(self, event_type: str, handler: callable) -> None:
        """Register a handler for an event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def emit(self, event_type: str, data: dict) -> None:
        """Emit an event to all registered handlers."""
        for handler in self._handlers.get(event_type, []):
            handler(data)
