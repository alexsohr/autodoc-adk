from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from src.database import engine as _engine_module
from src.database.engine import get_session_factory
from tests.e2e_seed.seed_playwright import seed_playwright


@pytest.fixture(autouse=True)
async def _reset_cached_engine():
    """Dispose the module-level engine after each test (per-loop binding)."""
    yield
    eng = getattr(_engine_module, "_engine", None)
    if eng is not None:
        await eng.dispose()
    if hasattr(_engine_module, "_engine"):
        _engine_module._engine = None
    if hasattr(_engine_module, "_session_factory"):
        _engine_module._session_factory = None


@pytest.mark.integration
async def test_seed_is_idempotent(tmp_path: Path):
    manifest = tmp_path / "seed.json"
    await seed_playwright(manifest_path=manifest)
    first = json.loads(manifest.read_text())

    factory = get_session_factory()
    async with factory() as session:
        n1 = (await session.execute(
            text("SELECT COUNT(*) FROM repositories WHERE seed_tag = 'playwright'")
        )).scalar()

    await seed_playwright(manifest_path=manifest)
    second = json.loads(manifest.read_text())
    factory = get_session_factory()
    async with factory() as session:
        n2 = (await session.execute(
            text("SELECT COUNT(*) FROM repositories WHERE seed_tag = 'playwright'")
        )).scalar()

    assert n1 == n2, f"row count changed: {n1} -> {n2}"
    assert first["repos"]["digitalClock"]["fullName"] == "Kalebu/Digital-clock-in-Python"
    assert second["repos"]["digitalClock"]["fullName"] == "Kalebu/Digital-clock-in-Python"


@pytest.mark.integration
async def test_seed_emits_required_keys(tmp_path: Path):
    manifest = tmp_path / "seed.json"
    await seed_playwright(manifest_path=manifest)
    data = json.loads(manifest.read_text())

    assert "repos" in data
    for slug in ("digitalClock", "debugRepo", "dbg2", "healthy", "running", "failed", "pending"):
        assert slug in data["repos"], f"missing repo slug: {slug}"
        repo = data["repos"][slug]
        assert "id" in repo and repo["id"]
        assert "name" in repo
        assert "fullName" in repo

    assert "jobs" in data
    assert "completedJobId" in data["jobs"] and data["jobs"]["completedJobId"]
