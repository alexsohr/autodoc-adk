# autodoc-adk Development Guidelines

Last updated: 2026-03-23

## Active Technologies
- PostgreSQL 18+ with pgvector extension (single instance: `autodoc` DB for app, `prefect` DB for Prefect Server); S3 for session archival
- Python 3.11+ + Google ADK, Prefect 3, FastAPI, SQLAlchemy 2.0 async + asyncpg, pgvector, Pydantic BaseSettings, OpenTelemetry, LiteLLM (via ADK's built-in LiteLlm wrapper), FastMCP
- Package manager: `uv` (not pip/poetry)

## Project Structure

```text
src/
  agents/              # ADK agents (structure_extractor, page_generator, readme_distiller)
    base.py            # BaseAgent[T](ABC, Generic[T]) — all agents subclass this
    common/            # AgentResult, EvaluationResult, QualityLoopConfig, run_quality_loop()
  api/                 # FastAPI app factory, routes, schemas, dependencies
    app.py             # create_app() with lifespan, exception handlers
    routes/            # health, repositories, jobs, documents, webhooks
    schemas/           # Pydantic request/response models
    dependencies.py    # FastAPI Depends providers (sessions, repos)
  config/              # Settings (BaseSettings singleton), get_model() factory, telemetry
  database/
    engine.py          # get_engine(), get_session_factory() — async SQLAlchemy
    models/            # ORM: Repository, Job, WikiStructure, WikiPage, PageChunk
    repos/             # Repository pattern: JobRepo, WikiRepo, RepositoryRepo, SearchRepo
    migrations/        # Alembic (001_initial_schema, 002_contextual_enrichment)
  flows/               # Prefect 3 flows and tasks
    full_generation.py # Full doc generation orchestrator
    incremental_update.py
    scope_processing.py # Per-scope worker (runs as K8s job)
    tasks/             # clone, discover, scan, structure, pages, readme, embeddings, pr, etc.
  providers/           # Git provider abstraction: GitHubProvider, BitbucketProvider
  services/            # chunking, embedding, search (hybrid RRF), config_loader
  errors.py            # TransientError, PermanentError, QualityError
  main.py              # Entry point — configures telemetry BEFORE ADK imports
  mcp_server.py        # FastMCP server
tests/
  unit/                # ~20+ test files, pytest + AsyncMock
  integration/         # test_api/, test_flows, test_agents, test_e2e_workflow
  contract/            # OpenAPI contract tests
deployment/
  Makefile             # All dev commands (see below)
  docker/              # Dockerfile.api, Dockerfile.worker, Dockerfile.flow, docker-compose files
  scripts/init-db.sql  # Creates prefect DB + pgvector extension
```

## Commands

```bash
# Install dependencies
uv sync

# Start dev infrastructure (PostgreSQL + Prefect)
cd deployment && make dev-up

# Run database migrations
cd deployment && make migrate

# Start API with hot reload (port 8080)
cd deployment && make api
# Equivalent: uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload --loop asyncio

# Start Prefect worker (local-dev pool)
cd deployment && make worker
# Equivalent: uv run prefect worker start --pool local-dev

# Deploy flows locally (create work pool + deploy)
cd deployment && make deploy-local

# Full stack via Docker
cd deployment && make up   # API:8080, Prefect:4200, PostgreSQL:5432
cd deployment && make down

# Run all tests
uv run pytest

# Run unit tests only
uv run pytest tests/unit/

# Run integration tests
uv run pytest tests/integration/ -m integration

# Run single test
uv run pytest tests/path/to/test.py::TestClass::test_name -x

# Lint
uv run ruff check src/ tests/

# Format check / fix
uv run ruff format --check src/ tests/
uv run ruff format src/ tests/
```

## Code Style

- Python 3.11+; all files start with `from __future__ import annotations`
- Type hints everywhere: `str | None` union syntax, `Mapped[type]` for SQLAlchemy, `Generic[T]`
- Async-first for all I/O operations
- Line length: 120 (ruff)
- Quote style: double quotes
- Ruff rules: E, W, F, I, N, UP, B, SIM, T20, RUF; ignores E501, B008 (FastAPI Depends)
- No type checker configured (no mypy/pyright)

## Architecture Patterns

- **Generator + Critic loop**: Each agent has separate Generator and Critic LlmAgents; Critic uses different model to avoid self-reinforcing bias
- **AgentResult[T]**: All agents return this wrapper with evaluation_history, attempts, scores, token_usage
- **Repository pattern**: `src/database/repos/` — one repo class per table, injected via FastAPI Depends
- **Factory functions**: `create_app()`, `get_provider()`, `get_model()`, `get_settings()`
- **Settings singleton**: `@lru_cache(maxsize=1) def get_settings() -> Settings:`
- **Telemetry must init first**: `configure_telemetry()` runs BEFORE any ADK import (ADK has built-in OpenTelemetry)
- **Error hierarchy**: TransientError (retryable → 503), PermanentError (fail fast → 400), QualityError (agent loop → 422)
- **Prefect task = transaction scope**: Each task is atomic; cross-task consistency via flow retry
- **Three work pools**: orchestrator-pool (K8s, limit 10), k8s-pool (K8s, limit 50), local-dev (process)
- **Three Docker images**: API (slim), Worker (Prefect base), Flow Runner (heavy, all AI libs + Node.js for MCP)
- **Hybrid search**: Reciprocal Rank Fusion (k=60) combining semantic (chunks) + full-text (pages)

## Testing Patterns

- pytest with `asyncio_mode = "auto"` — no manual event loop setup needed
- Class-based test organization: `class TestFeatureName:`
- Mocking: `unittest.mock.AsyncMock`, `MagicMock`, `@patch("src.module.func")`
- Test data via helper functions (e.g., `_make_litellm_response()`, `_fake_settings()`)
- Integration tests marked with `@pytest.mark.integration`

## Key Environment Variables

- `DATABASE_URL` — PostgreSQL connection string (asyncpg)
- `PREFECT_API_URL` — Prefect Server URL
- `GOOGLE_API_KEY` — For native Gemini models
- `DEFAULT_MODEL` — Fallback LLM (e.g., `gemini-2.5-flash`); per-agent overrides: `PAGE_GENERATOR_MODEL`, `PAGE_CRITIC_MODEL`, `STRUCTURE_GENERATOR_MODEL`, etc.
- `EMBEDDING_MODEL` — Default: `text-embedding-3-large`
- `CLONE_DIR` — Override temp directory for repo clones
- See `.env.example` for full list

## Recent Changes
- 001-autodoc-adk-docgen: Initial implementation — Google ADK agents, Prefect 3 flows, FastAPI, SQLAlchemy async, pgvector, LiteLLM, FastMCP


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
