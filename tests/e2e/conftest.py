from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from src.api.app import create_app
from src.api.dependencies import get_db_session

# Tables to truncate between tests (order respects FK constraints)
_TABLES_TO_TRUNCATE = [
    "page_chunks",
    "wiki_pages",
    "wiki_structures",
    "jobs",
    "repositories",
]


# ---------------------------------------------------------------------------
# 1.2  Session-scoped database fixture (testcontainers + Alembic migrations)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container with pgvector for the entire test session."""
    with PostgresContainer(
        image="pgvector/pgvector:pg17",
        username="test",
        password="test",
        dbname="autodoc_test",
    ) as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container) -> str:
    """Return an asyncpg-compatible connection URL for the test database."""
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://test:test@{host}:{port}/autodoc_test"


@pytest.fixture(scope="session")
def engine(database_url) -> AsyncEngine:
    """Create a session-scoped async engine connected to the test database."""
    return create_async_engine(database_url, echo=False, poolclass=NullPool)


@pytest.fixture(scope="session")
def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create a session-scoped async session factory."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def run_migrations(database_url, postgres_container):
    """Run Alembic migrations against the test database."""
    from alembic import command
    from alembic.config import Config

    from src.config.settings import Settings

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    alembic_cfg = Config(os.path.join(project_root, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(project_root, "src", "database", "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    test_settings = Settings(DATABASE_URL=database_url)
    with patch("src.config.settings.get_settings", return_value=test_settings):
        command.upgrade(alembic_cfg, "head")

    yield


# ---------------------------------------------------------------------------
# 1.3  Function-scoped cleanup fixture (truncation-based isolation)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_tables(engine):
    """Truncate all application tables after each test for isolation.

    Unlike SAVEPOINT-based isolation, this allows flow tasks to create
    independent sessions that can commit freely — essential because the
    Prefect flow code uses ``get_session_factory()`` to create sessions
    that commit independently of the API request session.
    """
    yield

    # Clean up after test
    async with engine.connect() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(_TABLES_TO_TRUNCATE)} CASCADE"))
        await conn.commit()


# ---------------------------------------------------------------------------
# 1.4  FastAPI test client fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh AsyncSession for API dependency overrides."""
    async with session_factory() as session:
        yield session


@pytest.fixture()
async def client(session_factory) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx.AsyncClient wired to a FastAPI app with test overrides.

    Only ``get_db_session`` is overridden — the original repo providers
    (``get_repository_repo``, ``get_job_repo``, etc.) use ``Depends(get_db_session)``
    and receive the test session automatically.  Each request gets a fresh session
    from the test engine that commits normally, so flow tasks and API handlers
    share the same database state.
    """
    app = create_app()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as request_session:
            try:
                yield request_session
                await request_session.commit()
            except Exception:
                await request_session.rollback()
                raise

    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1.5  Prefect test harness fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
async def prefect_harness(engine, session_factory):
    """Activate the Prefect test harness and patch DB engine/session factories.

    This lets Prefect flows and tasks run in-process with an ephemeral Prefect
    server, while still using the test database for application queries.

    Flows run as background tasks via ``asyncio.create_task()`` (the original
    ``_submit_flow`` behavior). Tests must poll ``GET /jobs/{id}`` to wait for
    completion. With truncation-based isolation and real commits, background
    tasks can see committed data.
    """
    from prefect.testing.utilities import prefect_test_harness

    from src.config.settings import Settings, get_settings

    get_settings.cache_clear()
    test_settings = Settings(AUTODOC_FLOW_DEPLOYMENT_PREFIX="dev")

    # Let the ORIGINAL _submit_flow run (asyncio.create_task) — the flow runs
    # as a background task AFTER the handler returns and the session commits.
    # With truncation-based isolation and real commits, background tasks see
    # committed data.  Tests must poll to wait for the flow to complete.
    with (
        prefect_test_harness(),
        patch.dict(os.environ, {"AUTODOC_FLOW_DEPLOYMENT_PREFIX": "dev"}),
        patch("src.config.settings.get_settings", return_value=test_settings),
        patch("src.database.engine.get_engine", return_value=engine),
        patch("src.database.engine.get_session_factory", return_value=session_factory),
    ):
        yield

    get_settings.cache_clear()
