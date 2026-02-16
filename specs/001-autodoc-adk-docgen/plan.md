# Implementation Plan: AutoDoc ADK Documentation Generator

**Branch**: `001-autodoc-adk-docgen` | **Date**: 2026-02-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-autodoc-adk-docgen/spec.md`

## Summary

Build a documentation generator that registers Git repositories, clones them, analyzes code structure via Google ADK agents with a Generator & Critic quality loop, produces wiki-style documentation pages (stored in PostgreSQL/pgvector), distills READMEs, and opens pull requests. Prefect 3 orchestrates all flows. A FastAPI REST API handles repository management, job lifecycle, documentation search, and webhook-driven updates. An MCP server exposes `find_repository` and `query_documents` for external AI agents.

## Technical Context

**Language/Version**: Python 3.11+
**Package Manager**: uv (not pip)
**Primary Dependencies**: Google ADK (with DatabaseSessionService, LoopAgent, LlmAgent), Prefect 3, FastAPI, SQLAlchemy async + asyncpg, pgvector, Pydantic BaseSettings, OpenTelemetry (TracerProvider + LoggingInstrumentor), LiteLLM (via ADK's built-in LiteLlm wrapper), FastMCP, Node.js 18+ (runtime prerequisite for @modelcontextprotocol/server-filesystem MCP server used by agents)
**Storage**: PostgreSQL 18+ with pgvector extension (single instance, two databases: `autodoc` for application, `prefect` for Prefect Server); S3/compatible for session archival only
**Testing**: pytest, prefect_test_harness, adk web (agent isolation testing)
**Target Platform**: Linux containers — Kubernetes in production, process work pool for local dev
**Project Type**: Single Python project
**Performance Goals**: Search queries < 3s (p95), Job management operations < 2s
**Constraints**: 1-hour hard timeout per job, MAX_CONCURRENT_JOBS=50 (work pool limit), MAX_REPO_SIZE=500MB, MAX_TOTAL_FILES=5000, MAX_FILE_SIZE=1MB
**Scale/Scope**: No hard ceiling on registered repositories or total wiki pages. Horizontal scaling via Kubernetes.

**Agent-MCP Architecture**:
- Agents (StructureExtractor, PageGenerator) access cloned repository files via a **filesystem MCP server** — no git MCP needed. The repo is cloned by Prefect tasks using subprocess git commands. Once cloned, ADK agents use `McpToolset` to connect to a local filesystem MCP server scoped to the clone directory.
- ReadmeDistiller works from generated wiki pages (passed via session state), no filesystem MCP needed.
- The **AutoDoc MCP server** is a single Python file using FastMCP (`fastmcp` library), exposing 2 tools: `find_repository` and `query_documents`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Agent Isolation | PASS | All ADK code in `src/agents/{name}/`. `BaseAgent` interface with `async run(input) -> AgentResult[output]`. Flows/API depend on BaseAgent only. |
| II | Generator & Critic Separation | PASS | Each agent module uses ADK `LoopAgent` with two `LlmAgent` sub-agents. Independent model config via env vars (`PAGE_GENERATOR_MODEL` vs `PAGE_CRITIC_MODEL`). |
| III | Quality-Gated Output (NON-NEGOTIABLE) | PASS | All output through Generator-Critic loop. Below `MINIMUM_SCORE_FLOOR` → job FAILED. Per-criterion floors enforced. Best attempt tracked. |
| IV | Prefect-First Orchestration | PASS | All workflows as Prefect flows/tasks. Task = atomic DB commit. No custom orchestration. Prefect UI as primary dashboard. |
| V | Concrete Data Layer | PASS | PostgreSQL + pgvector single DB. No abstract repository interfaces. Concrete SQLAlchemy async classes. FastAPI `Depends()` for DI. |
| VI | Structured Error Hierarchy | PASS | `TransientError`, `PermanentError`, `QualityError` hierarchy. Prefect retry keyed on error type. |
| VII | Observability by Design | PASS | JSON structured logs with `job_id`, `agent_name`, `task_name`. TracerProvider before ADK imports. LoggingInstrumentor for trace/span injection. Token usage in AgentResult, aggregated via `aggregate_job_metrics()`. |

**Technology & Infrastructure Constraints:**

| Constraint | Status | Notes |
|------------|--------|-------|
| Python 3.11+ | PASS | |
| Google ADK + DatabaseSessionService | PASS | Sessions in PostgreSQL, archived to S3, deleted after flow |
| Prefect 3 (work pools) | PASS | `local-dev` (process) + `k8s-pool` (kubernetes) + `orchestrator-pool` (kubernetes) |
| PostgreSQL 18+ / pgvector | PASS | Single instance, two DBs. vector(3072) for HNSW indexing. |
| SQLAlchemy async + asyncpg | PASS | `create_async_engine`, `async_sessionmaker`, `pool_pre_ping=True` |
| FastAPI async | PASS | All routes async. `Depends()` for injection. |
| Git Providers: GitHub + Bitbucket only | PASS | `GitProvider` interface + concrete implementations. No GitLab. |
| Ephemeral Workspaces | PASS | Temp dir per job, deleted on completion. S3 for session archival only. Orphan cleanup task. |
| 3 Docker images | PASS | API (lightweight), Worker (Prefect base), Flow Runner (heavy + AI libs). |
| Pydantic BaseSettings | PASS | All config via env vars. |
| No app-level auth | PASS | Deferred to reverse proxy. |
| No app-level rate limiting | PASS | Deferred to NGINX/cloud LB. |
| Cursor-based pagination | PASS | All list endpoints. |

**Development Workflow Gates:**

| Gate | Status | Notes |
|------|--------|-------|
| Agent testing via `adk web` | PASS | Each agent testable in isolation |
| Flow testing via `prefect_test_harness` | PASS | Full + incremental paths |
| API integration tests | PASS | pytest with test database |
| Transaction discipline (writes in task scope) | PASS | Each `@task` = one atomic commit |
| Job idempotency (partial unique index) | PASS | DB-level enforcement on `(repo_id, branch, dry_run)` WHERE active |
| .autodoc.yaml strict validation | PASS | Warn unknown keys, fail invalid values |
| Repo size enforcement | PASS | MAX_TOTAL_FILES, MAX_FILE_SIZE, MAX_REPO_SIZE in scan_file_tree |
| Version retention (max 3) | PASS | Application-level enforcement with cascade delete |

**Post-design re-check:** All principles confirmed compliant with Phase 1 artifacts (data-model.md, contracts/openapi.yaml).

## Project Structure

### Documentation (this feature)

```text
specs/001-autodoc-adk-docgen/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 technology research
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart guide
├── contracts/
│   └── openapi.yaml     # Phase 1 REST API contract
└── tasks.md             # Phase 2 task list (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── main.py                        # Entry point (telemetry init → FastAPI)
├── errors.py                      # TransientError, PermanentError, QualityError
├── mcp_server.py                  # FastMCP server: find_repository, query_documents
│
├── config/
│   ├── settings.py                # Pydantic BaseSettings (all env vars)
│   ├── models.py                  # get_model() factory (Gemini native / LiteLlm)
│   └── telemetry.py               # TracerProvider + LoggingInstrumentor setup
│
├── agents/
│   ├── base.py                    # BaseAgent interface: async run(input) -> AgentResult[T]
│   ├── common/
│   │   ├── agent_result.py        # AgentResult[T] dataclass
│   │   ├── evaluation.py          # EvaluationResult dataclass
│   │   ├── loop.py                # LoopAgent wrapper with score tracking + best-attempt
│   │   └── mcp_tools.py           # Filesystem MCP toolset factory (scoped to clone dir)
│   ├── structure_extractor/
│   │   ├── __init__.py
│   │   ├── agent.py               # StructureExtractor (BaseAgent impl)
│   │   ├── prompts.py             # System prompts + critic rubric
│   │   └── schemas.py             # WikiStructureSpec output
│   ├── page_generator/
│   │   ├── __init__.py
│   │   ├── agent.py               # PageGenerator (BaseAgent impl)
│   │   ├── prompts.py             # System prompts + critic rubric
│   │   └── schemas.py             # GeneratedPage output
│   └── readme_distiller/
│       ├── __init__.py
│       ├── agent.py               # ReadmeDistiller (BaseAgent impl)
│       ├── prompts.py             # System prompts + critic rubric
│       └── schemas.py             # ReadmeOutput
│
├── api/
│   ├── app.py                     # FastAPI app factory + lifespan
│   ├── dependencies.py            # Depends() providers (sessions, repos, services)
│   ├── routes/
│   │   ├── repositories.py        # CRUD + list
│   │   ├── jobs.py                # Create, list, get, cancel, retry, tasks, logs
│   │   ├── documents.py           # Wiki structure, pages, search, scopes
│   │   ├── webhooks.py            # POST /webhooks/push
│   │   └── health.py              # GET /health
│   └── schemas/
│       ├── repositories.py        # Pydantic request/response models
│       ├── jobs.py
│       ├── documents.py
│       └── common.py              # Pagination, error response
│
├── database/
│   ├── engine.py                  # create_async_engine + async_sessionmaker
│   ├── models/
│   │   ├── base.py                # DeclarativeBase
│   │   ├── repository.py          # Repository ORM model
│   │   ├── job.py                 # Job ORM model
│   │   ├── wiki_structure.py      # WikiStructure ORM model
│   │   ├── wiki_page.py           # WikiPage ORM model
│   │   └── page_chunk.py          # PageChunk ORM model
│   ├── repos/                     # Concrete data access (no abstract base)
│   │   ├── repository_repo.py     # RepositoryRepo
│   │   ├── job_repo.py            # JobRepo
│   │   ├── wiki_repo.py           # WikiRepo (structures + pages + chunks)
│   │   └── search_repo.py         # SearchRepo (text, semantic, hybrid/RRF)
│   └── migrations/
│       ├── env.py                 # Alembic async config
│       └── versions/              # Migration scripts
│
├── flows/
│   ├── full_generation.py         # full_generation_flow (orchestrator)
│   ├── incremental_update.py      # incremental_update_flow (orchestrator)
│   ├── scope_processing.py        # scope_processing_flow (worker, per-scope)
│   └── tasks/
│       ├── clone.py               # clone_repository → (repo_path, commit_sha)
│       ├── scan.py                # scan_file_tree (enforce size limits)
│       ├── discover.py            # discover_autodoc_configs → list[AutodocConfig]
│       ├── structure.py           # extract_structure → calls StructureExtractor
│       ├── pages.py               # generate_pages → calls PageGenerator per page
│       ├── readme.py              # distill_readme → calls ReadmeDistiller
│       ├── embeddings.py          # generate_embeddings → chunk + embed
│       ├── pr.py                  # create_pull_request, close_stale_autodoc_prs
│       ├── sessions.py            # archive_sessions (to S3), delete_sessions
│       ├── metrics.py             # aggregate_job_metrics
│       ├── cleanup.py             # cleanup_workspace (delete temp dir)
│       ├── callback.py            # deliver_callback (webhook to callback_url)
│       └── reconcile.py           # reconcile_stale_jobs (startup)
│
├── providers/
│   ├── base.py                    # GitProvider abstract interface
│   ├── github.py                  # GitHubProvider (clone, compare, PR)
│   └── bitbucket.py               # BitbucketProvider (clone, compare, PR)
│
└── services/
    ├── chunking.py                # Heading-aware markdown chunking (2-stage)
    ├── embedding.py               # Embedding generation (batch, text-embedding-3-large)
    ├── search.py                  # Search orchestrator (text, semantic, hybrid RRF)
    └── config_loader.py           # .autodoc.yaml parsing + strict validation

tests/
├── conftest.py                    # Shared fixtures (test DB, Prefect harness)
├── unit/
│   ├── test_chunking.py
│   ├── test_config_loader.py
│   ├── test_errors.py
│   ├── test_models_factory.py
│   └── test_schemas.py
├── integration/
│   ├── test_agents.py             # Generator-Critic loop integration
│   ├── test_flows.py              # Full + incremental via prefect_test_harness
│   ├── test_search.py             # Text, semantic, hybrid search
│   └── test_api/
│       ├── test_repositories.py
│       ├── test_jobs.py
│       ├── test_documents.py
│       └── test_webhooks.py
└── contract/
    └── test_openapi.py            # API response validation against OpenAPI spec

deployment/
├── scripts/
│   └── init-db.sql                # CREATE DATABASE prefect; CREATE EXTENSION vector;
├── docker/
│   ├── Dockerfile.api             # Lightweight API image
│   ├── Dockerfile.worker          # Prefect worker image
│   └── Dockerfile.flow            # Flow Runner image (heavy, AI libs)
├── docker-compose.yml             # Full stack
├── docker-compose.dev.yml         # Infrastructure only (PostgreSQL + Prefect Server)
└── Makefile                       # up, dev-up, api, worker, deploy-local, migrate, test

pyproject.toml                     # Project config (uv, dependencies, tool configs)
prefect.yaml                       # Deployment definitions (dev + prod)
alembic.ini                        # Alembic config
.env.example                       # Environment variable template
```

**Structure Decision**: Single Python project with `src/` layout. Agents isolated in `src/agents/`, flows in `src/flows/`, API in `src/api/`, data layer in `src/database/`. All agent code behind `BaseAgent` interface per Constitution Principle I. Database access via concrete classes (no repository abstraction) per Principle V. Git providers behind `GitProvider` interface per infrastructure constraints.

## Complexity Tracking

No constitution violations requiring justification. All principles pass.
