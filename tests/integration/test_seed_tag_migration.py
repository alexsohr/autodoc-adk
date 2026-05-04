from __future__ import annotations

import pytest
from sqlalchemy import text

from src.database.engine import get_session_factory


@pytest.mark.integration
async def test_repositories_has_seed_tag_column():
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                "SELECT column_name, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'repositories' AND column_name = 'seed_tag'"
            )
        )
        row = result.first()
        assert row is not None, "seed_tag column missing from repositories"
        assert row.is_nullable == "YES"


@pytest.mark.integration
async def test_seed_tag_index_exists():
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'repositories' AND indexname = 'ix_repositories_seed_tag'"
            )
        )
        assert result.first() is not None, "ix_repositories_seed_tag missing"
