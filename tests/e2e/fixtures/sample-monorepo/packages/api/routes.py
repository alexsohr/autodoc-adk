"""API route definitions."""

from __future__ import annotations


def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
