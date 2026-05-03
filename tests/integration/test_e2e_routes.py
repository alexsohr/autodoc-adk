from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.api.app import create_app
from src.config.settings import get_settings
from src.database.engine import get_session_factory


@pytest.mark.integration
async def test_reset_endpoint_returns_404_when_e2e_mode_off(monkeypatch):
    monkeypatch.setenv("AUTODOC_E2E", "0")
    get_settings.cache_clear()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/_e2e/reset")
        assert r.status_code == 404


@pytest.mark.integration
async def test_reset_endpoint_deletes_seeded_rows(monkeypatch):
    monkeypatch.setenv("AUTODOC_E2E", "1")
    get_settings.cache_clear()

    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            text(
                "INSERT INTO repositories "
                "(id, provider, url, org, name, branch_mappings, public_branch, seed_tag) "
                "VALUES (gen_random_uuid(), 'github', "
                "'https://github.com/pytest/seed-row', 'pytest', 'seed-row', "
                "'{}'::jsonb, 'main', 'playwright')"
            )
        )
        await session.commit()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/_e2e/reset")
        assert r.status_code == 200
        assert r.json() == {"deleted": True}

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM repositories WHERE seed_tag = 'playwright'")
        )
        assert result.scalar() == 0
