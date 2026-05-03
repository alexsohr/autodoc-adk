"""Shared fixtures for integration tests."""

from __future__ import annotations

import pytest

from src.database import engine as _engine_module


@pytest.fixture(autouse=True)
async def _reset_cached_engine():
    """Dispose the module-level engine after each test.

    pytest-asyncio (mode=auto) creates a new event loop per test. The
    process-wide engine cached in src.database.engine carries a connection
    bound to the first loop, which raises 'attached to a different loop'
    on subsequent tests. Disposing + clearing the cache forces re-creation
    on the next test's loop.
    """
    yield
    eng = getattr(_engine_module, "_engine", None)
    if eng is not None:
        await eng.dispose()
    if hasattr(_engine_module, "_engine"):
        _engine_module._engine = None
    if hasattr(_engine_module, "_session_factory"):
        _engine_module._session_factory = None
