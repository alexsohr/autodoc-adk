# autodoc-adk Development Guidelines

Last updated: 2026-04-04

## Active Technologies
- PostgreSQL 18+ with pgvector extension (single instance: `autodoc` DB for app, `prefect` DB for Prefect Server); S3 for session archival
- Python 3.11+ + Google ADK, Prefect 3, FastAPI, SQLAlchemy 2.0 async + asyncpg, pgvector, Pydantic BaseSettings, OpenTelemetry, LiteLLM (via ADK's built-in LiteLlm wrapper), FastMCP
- Package manager: `uv` (not pip/poetry)
- Frontend: React 19 + TypeScript (strict, `noUncheckedIndexedAccess`), Vite 6, Salt Design System (`@salt-ds/*`), TanStack Query, React Router v7
- Frontend package manager: `npm` (in `web/` directory)

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
  integration/         # test_api/, test_flows, test_agents
  e2e/                 # Deterministic E2E suite (86 scenarios, stub-based)
    stubs.py           # LLM/embedding/provider stubs for offline testing
    conftest.py        # Shared fixtures (app client, DB, sample repos)
    fixtures/          # sample-repo, sample-monorepo, sample-repo-v2, sample-repo-no-config
  contract/            # OpenAPI contract tests
web/                   # React dashboard (Vite + Salt DS + TypeScript)
  src/
    api/               # API client + TanStack Query hooks
    components/
      layout/          # AppLayout, TopBar, Sidebar, ContextSearch
      shared/          # Reusable: StatusBadge, MetricCard, DataTable, etc.
    contexts/          # AuthContext (role-based access)
    hooks/             # useLocalStorage, usePinnedRepos, useSidebarState
    pages/             # Route pages (RepoListPage, RepoWorkspace, etc.)
      tabs/            # Repo workspace tabs (Overview, Docs, Search, Jobs, etc.)
      admin/           # Admin pages (SystemHealth, AllJobs, UsageCosts, McpServers)
    theme/             # autodoc-theme.css (Stitch design tokens → Salt DS)
    types/             # TypeScript interfaces matching API schemas
    utils/             # Formatting utilities
  .storybook/          # Storybook config (loads Salt DS theme)
deployment/
  Makefile             # All dev commands (see below)
  docker/              # Dockerfile.api, Dockerfile.worker, Dockerfile.flow, Dockerfile.web, docker-compose files
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

# Run E2E tests (stub-based, no external services needed)
uv run pytest tests/e2e/ -m e2e

# Run single test
uv run pytest tests/path/to/test.py::TestClass::test_name -x

# Lint
uv run ruff check src/ tests/

# Format check / fix
uv run ruff format --check src/ tests/
uv run ruff format src/ tests/

# Frontend (run from web/)
cd web && npm install          # Install frontend deps
cd web && npm run dev           # Vite dev server (port 5173, proxies /api → 8080)
cd web && npm run build         # Production build
cd web && npm test              # Vitest
cd web && npm run storybook     # Storybook on port 6006

# Or from deployment/ via Makefile
cd deployment && make web-dev
cd deployment && make web-build
cd deployment && make web-test
cd deployment && make web-storybook

# E2E (Playwright UI tests, run from web/)
cd web && npm run test:e2e             # headless chromium
cd web && npm run test:e2e:ui          # Playwright UI mode
cd web && npm run test:e2e:headed      # headed
# Backend must be running with AUTODOC_E2E=1; see web/tests/e2e/README.md
```

## Code Style

- Python 3.11+; all files start with `from __future__ import annotations`
- Type hints everywhere: `str | None` union syntax, `Mapped[type]` for SQLAlchemy, `Generic[T]`
- Async-first for all I/O operations
- Line length: 120 (ruff)
- Quote style: double quotes
- Ruff rules: E, W, F, I, N, UP, B, SIM, T20, RUF; ignores E501, B008 (FastAPI Depends)
- No type checker configured (no mypy/pyright)

### Frontend (TypeScript)
- Strict mode with `noUncheckedIndexedAccess` — `array[0]` returns `T | undefined`
- Path aliases: `@/` → `src/` (configured in tsconfig + vite)
- Salt DS theme: custom CSS vars via `var(--autodoc-*)` in `autodoc-theme.css`
- Design rules: NO 1px borders (tonal layering), glassmorphism on floats, gradient CTA buttons
- Salt DS Dialog `onOpenChange` takes `(open: boolean)`, not event+detail pattern
- Storybook CSF3: stories with `render` override still need `args` when meta uses `satisfies Meta`
- Job status values are UPPERCASE in API responses (`"PENDING"`, `"RUNNING"`, `"COMPLETED"`, `"FAILED"`, `"CANCELLED"`) — frontend filter values must match
- `WikiPageResponse` does not include `section_path` or `scope_path` — guard with `?? []` when spreading

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
- **Four Docker images**: API (slim), Worker (Prefect base), Flow Runner (heavy, all AI libs + Node.js for MCP), Web (nginx + React SPA)
- **Hybrid search**: Reciprocal Rank Fusion (k=60) combining semantic (chunks) + full-text (pages)
- **Dashboard deployment**: `deployment/docker/Dockerfile.web` (NOT in `web/`), nginx serves SPA + proxies `/api`
- **API client pattern**: `web/src/api/client.ts` base fetch, `web/src/api/hooks.ts` TanStack Query hooks
- **Role-based UI**: AuthContext from `GET /auth/me` (SSO headers), RoleGate component for conditional rendering
- **Stitch design tokens**: Stitch project "Repo Landing Page" (ID: 17903516435494788863) is the source of truth for design
- **Enriched responses**: `RepositoryResponse` includes computed fields (`status`, `page_count`, `scope_count`, `avg_quality_score`, `last_generated_at`, `default_branch`) via `_enrich_repository_response()` helper in `src/api/routes/repositories.py`. Status derived from latest job: COMPLETED→healthy, RUNNING→running, FAILED→failed, no jobs→pending.
- **K8s image deploy**: Docker Desktop K8s caches images by tag. After rebuilding `autodoc-web:latest`, you must use a unique tag (e.g., `autodoc-web:v4`) and patch the deployment — `imagePullPolicy: IfNotPresent` won't pick up a rebuilt `:latest`
- **Web image rebuild**: `cd deployment && make web-docker` (or `docker build --no-cache -t autodoc-web -f deployment/docker/Dockerfile.web .` to bust cache)

## Testing Patterns

- pytest with `asyncio_mode = "auto"` — no manual event loop setup needed
- Class-based test organization: `class TestFeatureName:`
- Mocking: `unittest.mock.AsyncMock`, `MagicMock`, `@patch("src.module.func")`
- Test data via helper functions (e.g., `_make_litellm_response()`, `_fake_settings()`)
- Integration tests marked with `@pytest.mark.integration`
- E2E tests marked with `@pytest.mark.e2e`; fully deterministic via stubs (no LLM/DB needed)
- CI installs dev extras: `uv sync --extra dev` (no uv.lock committed)
- `test_mcp_server.py` skipped in CI (fastmcp version mismatch — pre-existing)

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
- E2E test suite: 86 deterministic scenarios across 9 test files, stub-based (no real LLM/DB), replaces prior 119 integration tests
- Dashboard UX design spec: docs/design/dashboard-ux-design-spec.md — chat UI, expanded MCP tooling for AI agents
- Dashboard UI: React 19 + Salt DS frontend in `web/`, 14 pages, 9 shared components, 13 new API endpoints, Storybook, K8s manifests
- fix-playwright-bugs: Enriched RepositoryResponse with computed fields, aligned AddRepo dialog to backend schema, fixed Jobs tab case mismatch, added error/empty states to Docs/Jobs tabs, implemented notifications dropdown and global search, fixed Mermaid rendering fallback


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
