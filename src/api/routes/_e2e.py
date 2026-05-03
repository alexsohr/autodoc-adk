"""Test-only endpoints. Mounted only when AUTODOC_E2E=1."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session

router = APIRouter(prefix="/_e2e", tags=["_e2e"])


@router.post("/reset")
async def reset_seeded_rows(session: AsyncSession = Depends(get_db_session)) -> dict[str, bool]:
    """Delete all rows tagged seed_tag='playwright'.

    Cascading FKs from repositories handle related jobs / wiki structures /
    wiki pages / page chunks. Idempotent.
    """
    await session.execute(
        text("DELETE FROM repositories WHERE seed_tag = 'playwright'")
    )
    return {"deleted": True}
