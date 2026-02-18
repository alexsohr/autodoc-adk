<!-- FOR AI AGENTS -->

# autodoc-adk

AI-powered documentation generator. Ingests source code repositories, uses LLM agents (Generator+Critic quality loops) to produce structured wiki documentation, and serves results via REST API. Built on Google ADK, Prefect 3, FastAPI, PostgreSQL/pgvector.

## Commands

```bash
# Lint
ruff check src/ tests/

# Format check
ruff format --check src/ tests/

# Format fix
ruff format src/ tests/

# Run all tests
pytest tests/

# Run single test
pytest tests/path/to/test.py::test_name -x

# Run API server (dev)
uvicorn src.main:app --reload
```

No type checker is configured. There is no mypy or pyright setup.

## File Map

```
src/
├── agents/                        # AI documentation agents
│   ├── base.py                    # BaseAgent ABC — all agents subclass this
│   ├── common/
│   │   ├── agent_result.py        # AgentResult[T] generic wrapper
│   │   ├── evaluation.py          # Critic evaluation data structures
│   │   ├── loop.py                # run_quality_loop() — Generator→Critic cycle
│   │   ├── mcp_tools.py           # MCP tool definitions for agents
│   │   └── prompts.py             # Shared prompt utilities (build_style_section)
│   ├── structure_extractor/       # Plans wiki structure from source tree
│   ├── page_generator/            # Generates individual doc pages
│   └── readme_distiller/          # Distills README from generated docs
├── api/
│   ├── app.py                     # create_app() factory
│   ├── dependencies.py            # FastAPI Depends providers
│   ├── routes/
│   │   ├── documents.py           # Wiki page retrieval + search
│   │   ├── health.py              # Health check
│   │   ├── jobs.py                # Job CRUD, cancel, retry
│   │   ├── repositories.py        # Repository CRUD
│   │   └── webhooks.py            # Push event receiver (GitHub/Bitbucket)
│   └── schemas/
│       ├── common.py              # Cursor pagination, shared types
│       ├── documents.py           # Document response models
│       ├── jobs.py                # Job request/response models
│       └── repositories.py        # Repository request/response models
├── config/
│   ├── models.py                  # get_model() factory — LiteLLM or native Gemini
│   ├── settings.py                # get_settings() Pydantic BaseSettings singleton
│   └── telemetry.py               # configure_telemetry() — MUST run before ADK import
├── database/
│   ├── engine.py                  # get_session_factory(), async engine setup
│   ├── migrations/                # Alembic migration versions
│   ├── models/
│   │   ├── base.py                # DeclarativeBase, common mixins
│   │   ├── job.py                 # Job model (PENDING→RUNNING→COMPLETED/FAILED/CANCELLED)
│   │   ├── page_chunk.py          # PageChunk model (vector embeddings)
│   │   ├── repository.py          # Repository model
│   │   ├── wiki_page.py           # WikiPage model
│   │   └── wiki_structure.py      # WikiStructure model
│   └── repos/
│       ├── job_repo.py            # Job DB operations
│       ├── repository_repo.py     # Repository DB operations
│       ├── search_repo.py         # Hybrid search (RRF = semantic + full-text)
│       └── wiki_repo.py           # WikiStructure/WikiPage/PageChunk DB operations
├── flows/
│   ├── full_generation.py         # Full doc generation orchestrator flow
│   ├── incremental_update.py      # Incremental update orchestrator flow
│   ├── scope_processing.py        # Per-scope worker flow (runs as K8s job)
│   └── tasks/
│       ├── callback.py            # Webhook callback delivery
│       ├── cleanup.py             # Stale PR cleanup, orphan workspace cleanup
│       ├── clone.py               # Repository cloning → (repo_path, commit_sha)
│       ├── discover.py            # .autodoc.yaml discovery across repo
│       ├── embeddings.py          # Chunk + embed wiki pages
│       ├── metrics.py             # aggregate_job_metrics()
│       ├── pages.py               # Page generation task (atomic per page)
│       ├── pr.py                  # PR creation on provider
│       ├── readme.py              # README distillation task
│       ├── reconcile.py           # Startup: sync RUNNING jobs vs Prefect states
│       ├── scan.py                # scan_file_tree with include/exclude patterns
│       ├── sessions.py            # ADK session archival to S3
│       └── structure.py           # Structure extraction task
├── providers/
│   ├── base.py                    # ProviderClient ABC + get_provider() factory
│   ├── github.py                  # GitHub API implementation (httpx)
│   └── bitbucket.py               # Bitbucket API implementation (httpx)
├── services/
│   ├── chunking.py                # chunk_markdown() — heading-aware + recursive fallback
│   ├── config_loader.py           # load_autodoc_config() — .autodoc.yaml parsing
│   ├── embedding.py               # generate_embeddings() — vector generation
│   └── search.py                  # Hybrid search orchestration
├── errors.py                      # TransientError, PermanentError, QualityError
├── main.py                        # FastAPI entry point (telemetry THEN app)
└── mcp_server.py                  # FastMCP server (find_repository, query_documents)

tests/
├── unit/                          # Isolated unit tests
├── integration/                   # Tests requiring DB/services
└── contract/                      # API contract tests
```

## Golden Samples

| For | Reference | Key patterns |
|-----|-----------|--------------|
| Agent implementation | `src/agents/page_generator/agent.py` | Generator+Critic loop, BaseAgent subclass, AgentResult return |
| Prefect flow | `src/flows/full_generation.py` | Orchestrator flow, task composition, error handling |
| Prefect task | `src/flows/tasks/pages.py` | `@task` decorator, atomic DB operations |
| API route | `src/api/routes/repositories.py` | FastAPI router, Depends injection, cursor pagination |
| DB repository | `src/database/repos/wiki_repo.py` | Async SQLAlchemy, repository pattern |
| DB model | `src/database/models/job.py` | SQLAlchemy ORM with mixins |
| Pydantic schema | `src/api/schemas/jobs.py` | Request/response models |
| Provider client | `src/providers/github.py` | ProviderClient ABC implementation, httpx |

## Utilities

| Need | Use | Location |
|------|-----|----------|
| LLM model instance | `get_model(model_name)` | `src/config/models.py` |
| App settings | `get_settings()` | `src/config/settings.py` |
| DB async session | `get_session_factory()` | `src/database/engine.py` |
| Git provider client | `get_provider(provider_name)` | `src/providers/base.py` |
| Style prompt fragment | `build_style_section(...)` | `src/agents/common/prompts.py` |
| Generator+Critic cycle | `run_quality_loop(...)` | `src/agents/common/loop.py` |
| Config file parsing | `load_autodoc_config(path)` | `src/services/config_loader.py` |
| Markdown chunking | `chunk_markdown(content, ...)` | `src/services/chunking.py` |
| Vector embeddings | `generate_embeddings(texts, ...)` | `src/services/embedding.py` |
| Error types | `TransientError`, `PermanentError`, `QualityError` | `src/errors.py` |
| Telemetry bootstrap | `configure_telemetry()` | `src/config/telemetry.py` |

## Heuristics

| When | Do |
|------|-----|
| Adding a new agent | Subclass `BaseAgent` in `src/agents/`, follow Generator+Critic pattern from `src/agents/page_generator/` |
| Adding API endpoint | Route in `src/api/routes/`, schema in `src/api/schemas/`, dependency in `src/api/dependencies.py` |
| Adding a Prefect task | Create in `src/flows/tasks/`, use `@task` decorator, keep DB operations atomic within the task |
| Adding DB model | Model in `src/database/models/`, then create Alembic migration with `alembic revision --autogenerate` |
| Error is retryable | Raise `TransientError` -- Prefect retries the task |
| Error is permanent | Raise `PermanentError` -- task fails immediately, no retry |
| Agent quality below threshold | Raise `QualityError` -- handled by the quality loop, not Prefect |
| Need an LLM model | Call `get_model()` factory -- never instantiate models directly |
| Need app config | Call `get_settings()` -- never use `os.environ` directly |
| Adding a new dependency | Ask first -- project minimizes dependencies |
| Modifying Alembic migrations | Ask first -- applied migrations must not change |
| Changing API schemas | Ask first -- affects downstream clients |
| Unsure about a pattern | Check Golden Samples table above |

## Terminology

| Term | Means |
|------|-------|
| Generator | LlmAgent that produces content (structure plan, doc page, README) |
| Critic | LlmAgent that evaluates Generator output against a weighted rubric |
| Quality loop | Generator then Critic, repeating up to N attempts until score threshold met |
| AgentResult | `AgentResult[T]` -- generic wrapper carrying typed output, evaluation_history, token_usage |
| Scope | Documentation boundary defined by `.autodoc.yaml` location; `scope_path='.'` for repo root |
| WikiStructure | Hierarchical plan of sections and pages for one scope |
| WikiPage | Single documentation page generated from source files |
| PageChunk | Embedding-sized fragment of WikiPage (512 tokens, 50 token overlap) |
| Provider | Git hosting abstraction (GitHub, Bitbucket) for clone, diff, PR operations |
| Orchestrator flow | Parent Prefect flow that fans out scope-level K8s jobs |
| Scope worker flow | `scope_processing_flow` -- independent K8s job per scope |
| Criterion floor | Per-criterion minimum score (e.g., accuracy >= 5.0) preventing high averages from masking failures |
| RRF | Reciprocal Rank Fusion -- hybrid search combining semantic chunk search + full-text page search |

## Critical Constraints

- **Telemetry before ADK**: `configure_telemetry()` MUST execute before any `google.adk` import. See `src/main.py` for the enforced ordering.
- **Async everywhere**: All DB access, HTTP calls, and provider operations use `async`/`await`. Never use synchronous DB calls.
- **Repository pattern for DB**: All database access goes through `src/database/repos/`. No raw SQL in routes or flows.
- **All agents return AgentResult[T]**: Never return raw dicts or untyped results from agent implementations.
- **Transaction scope = Prefect task**: Each `@task` is the atomic unit. Cross-task consistency relies on flow-level retry.
- **Ruff before commit**: Run `ruff check src/ tests/` and `ruff format --check src/ tests/` before every commit.
- **No secrets in repo**: Never commit `.env` files, credentials, or API keys.
- **Never modify applied migrations**: Files in `src/database/migrations/versions/` must not change after being applied to any environment.
- **FK cascade chain**: `wiki_structures` -> `wiki_pages` -> `page_chunks` all use `CASCADE DELETE`. Deleting a structure removes everything beneath it.

## Scope Index

Subdirectories may contain their own `AGENTS.md` with deeper context:

| Path | Covers |
|------|--------|
| `src/agents/AGENTS.md` | Agent implementations, quality loop, prompt patterns |
| `src/api/AGENTS.md` | FastAPI routes, schemas, dependency injection |
| `src/config/AGENTS.md` | Settings, model factory, telemetry setup |
| `src/database/AGENTS.md` | ORM models, repository pattern, migrations |
| `src/flows/AGENTS.md` | Prefect flows, tasks, orchestration patterns |
| `src/providers/AGENTS.md` | Git provider abstraction and implementations |
| `src/services/AGENTS.md` | Business logic: chunking, embedding, search, config loading |

## When Instructions Conflict

1. Subdirectory `AGENTS.md` files override this root file for their specific area.
2. Inline code comments override any `AGENTS.md` guidance.
3. `pyproject.toml` is the source of truth for tooling config (ruff rules, pytest settings, dependencies).
4. If `CLAUDE.md` and `AGENTS.md` conflict, follow whichever is more specific to the task at hand. `CLAUDE.md` carries project-wide architectural decisions; `AGENTS.md` carries operational instructions for working in the codebase.
5. When in doubt, match the pattern in the closest Golden Sample rather than inventing a new approach.
