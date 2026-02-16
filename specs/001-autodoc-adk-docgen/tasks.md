# Tasks: AutoDoc ADK Documentation Generator

**Input**: Design documents from `/specs/001-autodoc-adk-docgen/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/openapi.yaml

**Tests**: Three minimal test tasks included per constitution requirements (adk web agent testing, prefect_test_harness flow testing, API integration testing). Each implementation task implicitly includes writing corresponding unit tests (e.g., T039 config_loader → tests/unit/test_config_loader.py, T005 errors → tests/unit/test_errors.py). Full TDD test suite built incrementally alongside implementation.

**Organization**: Tasks grouped by user story. US3 (Quality-Gated Generation) is embedded in US1 since the Generator & Critic loop is the core mechanism of all agent implementations.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US9)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Deployment: `deployment/`
- Configuration: `pyproject.toml`, `alembic.ini`, `prefect.yaml`, `.env.example`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure with all directories from plan.md (`src/config/`, `src/agents/common/`, `src/agents/structure_extractor/`, `src/agents/page_generator/`, `src/agents/readme_distiller/`, `src/api/routes/`, `src/api/schemas/`, `src/database/models/`, `src/database/repos/`, `src/database/migrations/versions/`, `src/flows/tasks/`, `src/providers/`, `src/services/`, `tests/unit/`, `tests/integration/test_api/`, `tests/contract/`, `deployment/scripts/`, `deployment/docker/`) with `__init__.py` files
- [x] T002 Initialize pyproject.toml with uv, Python 3.11+ requirement, and all dependencies (google-adk, prefect>=3.0, fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, pgvector, pydantic-settings, opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc, opentelemetry-instrumentation-logging, litellm, fastmcp, httpx, boto3, alembic) and dev dependencies (pytest, pytest-asyncio, ruff). Ensure Node.js 18+ is listed as a runtime prerequisite in pyproject.toml metadata and .env.example comments (required for @modelcontextprotocol/server-filesystem MCP server used by agents)
- [x] T003 [P] Create .env.example with all configuration variables per quickstart.md (DATABASE_URL, PREFECT_API_URL, model vars, embedding vars, provider credentials, session archival)
- [x] T004 [P] Configure ruff linting rules and formatting in pyproject.toml `[tool.ruff]` section

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Implement error hierarchy with TransientError (retryable), PermanentError (fail fast), and QualityError (agent loop handles) as Exception subclasses in src/errors.py
- [x] T006 [P] Implement Pydantic BaseSettings with all env vars (DATABASE_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT, DB_POOL_RECYCLE, PREFECT_API_URL, PREFECT_WORK_POOL, AUTODOC_FLOW_DEPLOYMENT_PREFIX, APP_COMMIT_SHA, DEFAULT_MODEL, per-agent model vars, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, quality thresholds, repo size limits, chunk settings) in src/config/settings.py
- [x] T007 [P] Implement OpenTelemetry setup: TracerProvider with OTLPSpanExporter + BatchSpanProcessor, LoggingInstrumentor for trace/span injection into logs, service resource metadata — MUST be callable before any ADK imports — in src/config/telemetry.py and JSON structured logging configuration with python-json-logger (or equivalent) including custom filter that injects job_id, agent_name, and task_name correlation fields into all log records per constitution Principle VII
- [x] T008 [P] Implement get_model() factory that returns raw string for native gemini-* models and LiteLlm instance for provider-prefixed strings (vertex_ai/*, azure/*, bedrock/*) per research.md Section 16 in src/config/models.py
- [x] T009 Implement async database engine with create_async_engine (asyncpg driver, configurable pool_size/max_overflow/pool_timeout/pool_recycle via settings, pool_pre_ping=True) and async_sessionmaker (expire_on_commit=False) in src/database/engine.py
- [x] T010 Create SQLAlchemy DeclarativeBase with common column mixins (id UUID PK with gen_random_uuid, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ) in src/database/models/base.py
- [x] T011 [P] Create Repository ORM model with all columns from data-model.md (provider CHECK, url UNIQUE, org, name, branch_mappings JSONB, public_branch, access_token nullable) in src/database/models/repository.py
- [x] T012 [P] Create Job ORM model with all columns from data-model.md (status/mode CHECK constraints, commit_sha, force, dry_run, prefect_flow_run_id, app_commit_sha, quality_report/token_usage/config_warnings JSONB, callback_url, error_message, pull_request_url) and partial unique index on (repository_id, branch, dry_run) WHERE status IN (PENDING, RUNNING) in src/database/models/job.py
- [x] T013 [P] Create WikiStructure ORM model with unique constraint on (repository_id, branch, scope_path, version), FK to repositories CASCADE, FK to jobs SET NULL, sections JSONB in src/database/models/wiki_structure.py
- [x] T014 [P] Create WikiPage ORM model with FK to wiki_structures CASCADE, page_key unique within structure, importance/page_type CHECK constraints, source_files/related_pages JSONB, content TEXT, quality_score FLOAT, unique constraint on (wiki_structure_id, page_key), GIN index on to_tsvector('english', content) in src/database/models/wiki_page.py
- [x] T015 [P] Create PageChunk ORM model with FK to wiki_pages CASCADE, vector(3072) content_embedding column, HNSW index with vector_cosine_ops, unique constraint on (wiki_page_id, chunk_index), heading_path TEXT ARRAY, token_count, start_char/end_char, has_code in src/database/models/page_chunk.py
- [x] T016 Configure Alembic for async migrations (asyncpg driver, target_metadata from all models) in alembic.ini and src/database/migrations/env.py, then generate initial migration with all tables, indexes, and constraints
- [x] T017 [P] Implement RepositoryRepo with create, get_by_id, get_by_url, list (cursor-based pagination), update, delete methods in src/database/repos/repository_repo.py
- [x] T018 [P] Implement JobRepo with create (idempotency check via partial unique index), get_by_id, list (filtered by repository_id/status/branch with cursor pagination), update_status (enforce valid transitions), get_active_for_repo methods in src/database/repos/job_repo.py
- [x] T019 [P] Implement WikiRepo with create_structure (version retention: delete oldest when 4th created per scope), create_pages (batch insert), create_chunks (batch insert), get_latest_structure (by repo+branch+scope), get_page_by_key, get_structures_for_repo methods in src/database/repos/wiki_repo.py
- [x] T020 Implement FastAPI app factory with async lifespan (database engine disposal on shutdown), structured exception handlers mapping TransientError→503, PermanentError→400, QualityError→422, and include routers in src/api/app.py
- [x] T021 [P] Implement API dependency providers (get_db_session, get_repository_repo, get_job_repo, get_wiki_repo via Depends) in src/api/dependencies.py and common Pydantic schemas (PaginatedResponse with next_cursor/limit, ErrorResponse with detail) in src/api/schemas/common.py
- [x] T022 Implement health check endpoint GET /health checking database connectivity, Prefect API reachability, and OTel exporter status per openapi.yaml HealthResponse schema in src/api/routes/health.py
- [x] T023 Implement application entry point: call configure_telemetry() BEFORE any ADK imports, then create and run FastAPI app with uvicorn in src/main.py
- [x] T024 Create deployment infrastructure: init-db.sql (CREATE DATABASE prefect + CREATE EXTENSION vector on autodoc), docker-compose.dev.yml (PostgreSQL pgvector + Prefect Server with healthchecks), and Makefile (dev-up, migrate, api, worker, deploy-local, test targets) in deployment/

**Checkpoint**: Foundation ready — `make dev-up && make migrate && make api` should start a working (empty) API server with health check passing

---

## Phase 3: User Story 1 + User Story 3 — Full Documentation Generation + Quality-Gated Agents (Priority: P1) :dart: MVP

**Goal**: Register a repository, trigger full documentation generation with quality-gated Generator & Critic agents, get wiki pages stored in PostgreSQL and a README pull request.

**Independent Test**: Register a sample repository via POST /repositories, trigger POST /jobs, wait for completion, verify wiki pages exist via WikiRepo and PR is created with README.

**Note**: US3 (Quality-Gated Generation) is embedded here — the Generator & Critic loop with LoopAgent, per-criterion floors, best-attempt tracking, and critic failure resilience IS how all agents work.

### API Layer

- [ ] T025 [P] [US1] Implement repository API schemas (RegisterRepositoryRequest, UpdateRepositoryRequest, RepositoryResponse with all fields per openapi.yaml) and CRUD routes (POST /repositories, GET /repositories with cursor pagination, GET /repositories/{id}, PATCH /repositories/{id}, DELETE /repositories/{id} with 204) in src/api/schemas/repositories.py and src/api/routes/repositories.py
- [ ] T026 [P] [US1] Implement job API schemas (CreateJobRequest with repository_id/branch/force/dry_run/callback_url, JobResponse with all fields, JobStatus enum, JobMode enum, QualityReport, TokenUsage, AgentTokenUsage, WikiStructureResponse, TaskState, LogEntry per openapi.yaml) in src/api/schemas/jobs.py
- [ ] T027 [US1] Implement job routes: POST /jobs (auto-determine full/incremental: if force=true, mode is always full and routes to full_generation_flow; otherwise check if any wiki_structures exist for (repository_id, branch) — if none exist, mode is full; if they exist, mode is incremental, populate app_commit_sha from settings.APP_COMMIT_SHA into the job record at creation, default branch to repository's public_branch if omitted, enforce branch in branch_mappings, idempotency returning 200 for existing active job, 201 for new), GET /jobs/{id}, GET /jobs/{id}/structure in src/api/routes/jobs.py

### Provider Layer

- [ ] T028 [US1] Implement GitProvider abstract interface with async methods: clone_repository(url, branch, access_token, dest_dir) -> (path, sha), create_pull_request(url, branch, target_branch, title, body, access_token, reviewers, auto_merge) -> pr_url, close_stale_prs(url, branch_pattern, access_token), compare_commits(url, base_sha, head_sha, access_token) -> list[str] in src/providers/base.py
- [ ] T029 [P] [US1] Implement GitHubProvider: clone via subprocess git (inject token in URL for private repos), create PR via GitHub REST API (httpx, enable auto-merge via GraphQL mutation if auto_merge=True), close stale autodoc PRs matching branch pattern autodoc/{repo_name}-{branch}-*, extract org/name from URL in src/providers/github.py
- [ ] T030 [P] [US1] Implement BitbucketProvider: clone via subprocess git (inject token in URL for private repos), create PR via Bitbucket REST API (httpx, set close_source_branch and auto-merge if auto_merge=True), close stale autodoc PRs, extract org/name from URL in src/providers/bitbucket.py

### Agent Infrastructure (US3 Quality Gating embedded)

- [ ] T031 [US1] Implement BaseAgent abstract class with abstract async method `run(input, session_service, session_id) -> AgentResult[T]` and helper methods for model configuration in src/agents/base.py
- [ ] T032 [P] [US1] Implement AgentResult[T] generic dataclass with fields: output (T), attempts (int), final_score (float), passed_quality_gate (bool), below_minimum_floor (bool), evaluation_history (list[EvaluationResult]), token_usage (TokenUsage dataclass with input/output/total tokens and calls count) in src/agents/common/agent_result.py
- [ ] T033 [P] [US1] Implement EvaluationResult dataclass with fields: score (float 1-10), passed (bool), feedback (str), criteria_scores (dict[str, float]), criteria_weights (dict[str, float]) in src/agents/common/evaluation.py
- [ ] T034 [US1] Implement quality-gated LoopAgent wrapper: create ADK LoopAgent with generator LlmAgent + critic LlmAgent sub-agents, critic uses exit_loop tool (escalate=True, skip_summarization=True) to signal pass, track best attempt (highest score) across iterations, enforce overall quality_threshold (default 7.0) + per-criterion minimum floors (configurable via settings), auto-pass on critic LLM failure with warning logged, extract token usage from session events, return AgentResult in src/agents/common/loop.py
- [ ] T035 [US1] Implement filesystem MCP toolset factory: create McpToolset via McpToolset.from_server with StdioServerParams(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", repo_path]), return (tools, exit_stack) for cleanup in src/agents/common/mcp_tools.py

### Agent Implementations

- [ ] T036 [US1] Implement StructureExtractor agent: BaseAgent subclass, generator LlmAgent with filesystem MCP tools analyzes repository structure and produces WikiStructureSpec (sections hierarchy with page specs per data-model.md sections JSONB schema), critic LlmAgent evaluates coverage/organization/granularity against weighted rubric, configurable via STRUCTURE_GENERATOR_MODEL and STRUCTURE_CRITIC_MODEL env vars in src/agents/structure_extractor/ (agent.py, prompts.py, schemas.py, __init__.py)
- [ ] T037 [US1] Implement PageGenerator agent: BaseAgent subclass, generator LlmAgent with filesystem MCP tools reads source files and produces GeneratedPage (title, content markdown, quality metadata), critic LlmAgent receives source_context via session state and evaluates accuracy/completeness/clarity against weighted rubric, configurable via PAGE_GENERATOR_MODEL and PAGE_CRITIC_MODEL in src/agents/page_generator/ (agent.py, prompts.py, schemas.py, __init__.py)
- [ ] T038 [US1] Implement ReadmeDistiller agent: BaseAgent subclass, generator LlmAgent (NO filesystem tools, works from wiki pages passed via session state) produces ReadmeOutput (distilled markdown README), critic LlmAgent evaluates conciseness/accuracy/structure, configurable via README_GENERATOR_MODEL and README_CRITIC_MODEL in src/agents/readme_distiller/ (agent.py, prompts.py, schemas.py, __init__.py)

### Services

- [ ] T039 [US1] Implement .autodoc.yaml config loader: parse YAML into AutodocConfig dataclass (version, include, exclude, style with audience/tone/detail_level, custom_instructions, readme with output_path/max_length/include_toc/include_badges, pull_request with auto_merge/reviewers), warn on unknown keys, raise PermanentError on invalid values, return sensible defaults when no config file exists in src/services/config_loader.py

### Flow Tasks

- [ ] T040 [P] [US1] Implement clone_repository Prefect task: resolve GitProvider from repository record, clone to temp dir (tempfile with autodoc_ prefix), extract commit SHA from HEAD, return (repo_path, commit_sha) in src/flows/tasks/clone.py
- [ ] T041 [P] [US1] Implement scan_file_tree Prefect task: walk cloned repo directory, enforce MAX_REPO_SIZE/MAX_TOTAL_FILES/MAX_FILE_SIZE limits (raise PermanentError on violation), apply include/exclude patterns from AutodocConfig, warn if pruning removes >90% of files, return filtered file path list in src/flows/tasks/scan.py
- [ ] T042 [US1] Implement discover_autodoc_configs Prefect task: look for .autodoc.yaml in repo root, parse with config_loader, return list with single AutodocConfig (scope_path="."), store any config warnings in job record via JobRepo in src/flows/tasks/discover.py
- [ ] T043 [US1] Implement extract_structure Prefect task: create DatabaseSessionService session (user_id=job_id), run StructureExtractor agent with file list and config, save WikiStructure to DB via WikiRepo (enforce version retention), return AgentResult[WikiStructureSpec] in src/flows/tasks/structure.py
- [ ] T044 [US1] Implement generate_pages Prefect task: iterate page specs from WikiStructureSpec, run PageGenerator agent for each page with source files, save each WikiPage to DB via WikiRepo (atomic per page — partial results persist on failure), collect and return list of AgentResults in src/flows/tasks/pages.py
- [ ] T045 [US1] Implement distill_readme Prefect task: load generated wiki pages into session state, run ReadmeDistiller agent, return AgentResult[ReadmeOutput] with README markdown in src/flows/tasks/readme.py
- [ ] T046 [P] [US1] Implement PR tasks: create_pull_request (create branch autodoc/{repo_name}-{branch}-{job_id_short}-{YYYY-MM-DD}, commit README file, push, create PR targeting configured target branch via GitProvider, pass auto_merge from AutodocConfig.pull_request.auto_merge) and close_stale_autodoc_prs (close existing open autodoc/* PRs for same repo+branch before creating new one) in src/flows/tasks/pr.py
- [ ] T047 [P] [US1] Implement session tasks: archive_sessions (export ADK session data from DatabaseSessionService to S3 as JSON using boto3) and delete_sessions (remove sessions from PostgreSQL after successful archival) in src/flows/tasks/sessions.py
- [ ] T048 [P] [US1] Implement aggregate_job_metrics Prefect task: collect token_usage and quality scores from all AgentResults across structure/pages/readme and embedding service calls, build quality_report JSONB (overall_score, per_page_scores, pages_below_floor, readme_score, structure_score) and token_usage JSONB (totals + per-agent breakdown including embedding token usage), update job record in src/flows/tasks/metrics.py
- [ ] T049 [P] [US1] Implement cleanup_workspace Prefect task: delete temporary clone directory (autodoc_* prefix path), log cleanup result in src/flows/tasks/cleanup.py (in K8s production, workspace cleanup is handled by ephemeral pod volumes; this task provides explicit cleanup for local dev and as a safety net)

### Flows

- [ ] T050 [US1] Implement scope_processing_flow: Prefect @flow that processes a single documentation scope — extract_structure → check structure quality gate (if AgentResult.below_minimum_floor is True, raise QualityError immediately — skip page generation) → (if not dry_run: generate_pages → distill_readme) sequentially (generate_embeddings is added in parallel with distill_readme by T066 in Phase 7), set timeout_seconds=3600 on @flow decorator with try/finally block ensuring job status is updated to FAILED with timeout reason before flow termination (note: in K8s production, also set activeDeadlineSeconds=3660 on pod spec as a backup enforcement mechanism), accepts (repository_id, job_id, branch, scope_path, commit_sha, repo_path, config) parameters, returns scope results in src/flows/scope_processing.py
- [ ] T051 [US1] Implement full_generation_flow: Prefect @flow orchestrator — update job PENDING→RUNNING → clone_repository → scan_file_tree → discover_autodoc_configs → call scope_processing_flow (single scope) → close_stale_prs → create_pull_request → aggregate_job_metrics → check quality gate (if any agent output has below_minimum_floor — pages, structure, or README — mark job FAILED with quality gate error instead of COMPLETED) → if dry_run, skip PR creation and session archival → archive_sessions → delete_sessions → cleanup_workspace → update job to COMPLETED with quality_report/token_usage/pull_request_url (or FAILED with error_message on exception) → if callback_url is set, deliver_callback, set timeout_seconds=3600 on @flow decorator with try/finally block ensuring job status is updated to FAILED with timeout reason if TimeoutError is raised (note: in K8s production, also set activeDeadlineSeconds=3660 on pod spec as a backup enforcement mechanism) in src/flows/full_generation.py
- [ ] T052 [US1] Create prefect.yaml with deployment definitions: dev-full-generation (local-dev pool), prod-full-generation (orchestrator-pool), dev-scope-processing (local-dev pool), prod-scope-processing (k8s-pool) per research.md Section 3 patterns
- [ ] T052b [US1] Add work pool concurrency limit configuration to Makefile deploy-local target: `prefect work-pool set-concurrency-limit k8s-pool 50` for production and document MAX_CONCURRENT_JOBS=50 in .env.example per FR-027

**Checkpoint**: Full pipeline works end-to-end: register repo → trigger job → wiki pages in DB → README PR created

---

## Phase 4: User Story 2 — Incremental Documentation Update (Priority: P1)

**Goal**: After initial documentation exists (commit SHA stored), detect changed files via provider compare API and regenerate only affected pages.

**Independent Test**: Run full generation first (stores commit_sha), modify source files, trigger new job. System auto-detects incremental mode, regenerates only affected pages, creates updated PR.

**Depends on**: US1 (requires prior full generation with stored commit_sha)

- [ ] T053 [US2] Implement compare_commits in GitHubProvider (GitHub compare API: GET /repos/{owner}/{repo}/compare/{base}...{head}) and BitbucketProvider (Bitbucket diffstat API: GET /repositories/{workspace}/{slug}/diffstat/{spec}) — return list of changed file paths between two SHAs in src/providers/github.py and src/providers/bitbucket.py
- [ ] T054 [US2] Implement incremental_update_flow: Prefect @flow orchestrator — get baseline SHA (min commit_sha across existing wiki_structures for repo+branch), compare_commits via provider API, short-circuit with job status no_changes if no diff and force=false, clone repo, detect structural changes (new modules/deleted dirs needing structure re-extraction), regenerate only pages whose source_files intersect changed files, duplicate unchanged WikiPage records from the latest WikiStructure into the new version (required because WikiPage FK references wiki_structure_id with CASCADE DELETE), create new WikiStructure version, follow same PR/metrics/cleanup pattern as full_generation_flow, aggregate_job_metrics → check quality gate (if any agent output has below_minimum_floor — pages, structure, or README — mark job FAILED with quality gate error instead of COMPLETED), if callback_url is set, deliver_callback → support dry_run=True, set timeout_seconds=3600 on @flow decorator in src/flows/incremental_update.py
- [ ] T055 [US2] Add incremental_update_flow deployment definitions (dev-incremental + prod-incremental) to prefect.yaml and update POST /jobs route to trigger incremental_update_flow when wiki_structures exist for the (repository_id, branch) in src/api/routes/jobs.py

**Checkpoint**: Incremental updates regenerate only changed pages and complete faster than full generation for small changesets

---

## Phase 5: User Story 4 — Repository Configuration via .autodoc.yaml (Priority: P2)

**Goal**: .autodoc.yaml customization options (include/exclude, style, custom_instructions, readme settings) actively affect documentation generation output.

**Independent Test**: Create repository with .autodoc.yaml specifying `include: ["src/"]`, `exclude: ["*.test.*"]`, `style.audience: "senior-developer"`, and `custom_instructions`. Verify only src/ files (excluding tests) are documented in the specified style.

**Depends on**: US1 (requires working pipeline)

- [ ] T056 [US4] Integrate include/exclude glob patterns from AutodocConfig into scan_file_tree: apply include patterns first (empty = all files), then subtract exclude patterns, log file count before/after filtering in src/flows/tasks/scan.py
- [ ] T057 [US4] Inject style preferences (audience, tone, detail_level) and custom_instructions text into all agent system prompts — update prompts.py in each agent module (structure_extractor, page_generator, readme_distiller) to accept AutodocConfig and incorporate style/instructions into the prompt template in src/agents/structure_extractor/prompts.py, src/agents/page_generator/prompts.py, and src/agents/readme_distiller/prompts.py
- [ ] T058 [US4] Integrate readme config into pipeline: apply max_length (word cap) and include_toc/include_badges preferences in ReadmeDistiller prompt, commit README to configured output_path (relative to .autodoc.yaml directory) in PR task in src/agents/readme_distiller/prompts.py and src/flows/tasks/pr.py

**Checkpoint**: Configuration options from .autodoc.yaml visibly affect generated documentation style and scope

---

## Phase 6: User Story 5 — Monorepo Support (Priority: P2)

**Goal**: Multiple .autodoc.yaml files in a monorepo are discovered and processed as independent scopes with separate wiki structures and READMEs in a single PR.

**Independent Test**: Create repository with .autodoc.yaml at root and in packages/auth/. Trigger generation. Verify two separate wiki structures exist per scope and one PR contains both READMEs at their configured output_path locations.

**Depends on**: US1 (pipeline), US4 (.autodoc.yaml integration)

- [ ] T059 [US5] Extend discover_autodoc_configs to recursively find all .autodoc.yaml files in the cloned repository, return list of AutodocConfig objects with scope_path set to the relative directory path (e.g., ".", "packages/auth") in src/flows/tasks/discover.py
- [ ] T060 [US5] Implement scope overlap auto-exclusion: when a parent scope directory contains child scope directories with their own .autodoc.yaml, auto-add those child directories to the parent's exclude list to prevent duplicate documentation in src/services/config_loader.py
- [ ] T061 [US5] Implement parallel scope fan-out: update full_generation_flow and incremental_update_flow to process multiple scopes — use run_deployment() for K8s (prod) or asyncio.gather with direct subflow calls (dev), collect results from all scope flows, create single PR with all scope READMEs in src/flows/full_generation.py and src/flows/incremental_update.py
- [ ] T062 [US5] Implement list scopes endpoint GET /documents/{repo_id}/scopes returning ScopesResponse (list of ScopeInfo with scope_path, title, description, page_count) with optional branch query parameter per openapi.yaml in src/api/routes/documents.py

**Checkpoint**: Monorepo with multiple scopes produces independent wiki structures per scope and a combined PR

---

## Phase 7: User Story 6 — Documentation Search (Priority: P2)

**Goal**: Users can search generated documentation using text, semantic, or hybrid (RRF) search with <3s p95 latency.

**Independent Test**: After generating documentation, perform text search (keyword), semantic search (natural language), and hybrid search via GET /documents/{repo_id}/search. Verify relevant results with chunk-level context.

**Depends on**: US1 (requires generated wiki pages to search)

- [ ] T063 [P] [US6] Implement heading-aware markdown chunking service: Stage 1 splits by markdown headings (never split inside fenced code blocks or tables), Stage 2 recursively splits oversized sections (>CHUNK_MAX_TOKENS=512) with separators ["\n\n", "\n", ". ", " "] and CHUNK_OVERLAP_TOKENS=50 overlap, merge sub-minimum chunks (< CHUNK_MIN_TOKENS=50), compute token_count via cl100k_base encoding, track heading_path/heading_level/start_char/end_char/has_code metadata per chunk in src/services/chunking.py
- [ ] T064 [P] [US6] Implement embedding generation service: batch embed text chunks using configurable model (default text-embedding-3-large, 3072 dimensions via settings), respect EMBEDDING_BATCH_SIZE=100, use litellm.aembedding() for multi-provider embedding support (consistent with LLM layer), return list of embedding vectors in src/services/embedding.py
- [ ] T065 [US6] Implement generate_embeddings Prefect task: load all wiki pages for a scope, chunk each page via chunking service, embed all chunks via embedding service, save PageChunk records (content, content_embedding, heading metadata) to DB via WikiRepo batch insert in src/flows/tasks/embeddings.py
- [ ] T066 [US6] Add generate_embeddings to scope_processing_flow running in parallel with distill_readme via asyncio.gather after generate_pages completes in src/flows/scope_processing.py
- [ ] T067 [US6] Implement SearchRepo: text_search (ts_rank on GIN index with plainto_tsquery, filter by repo+branch+scope, latest version), semantic_search (pgvector cosine on page_chunks with best-chunk-wins aggregation via PARTITION BY wiki_page_id), hybrid_search (RRF with k=60 combining text ranks + semantic ranks via FULL OUTER JOIN, penalty rank 1000 for absent pages) per data-model.md SQL patterns in src/database/repos/search_repo.py
- [ ] T068 [US6] Implement search orchestrator service: accept query/search_type/repo_id/branch/scope/limit, default branch to repository's public_branch, generate query embedding for semantic/hybrid via embedding service, delegate to SearchRepo, format results with snippets and best_chunk metadata in src/services/search.py
- [ ] T069 [P] [US6] Implement document API schemas (WikiSection, WikiPageSummary, WikiPageResponse, PaginatedWikiResponse, SearchResponse, SearchResult with best_chunk_content/best_chunk_heading_path, ScopeInfo, ScopesResponse per openapi.yaml) in src/api/schemas/documents.py
- [ ] T070 [US6] Implement document routes: GET /documents/{repo_id} (paginated wiki sections from latest structure), GET /documents/{repo_id}/pages/{page_key} (full page content+metadata), GET /documents/{repo_id}/search (text/semantic/hybrid with branch+scope query params, default to public_branch) per openapi.yaml in src/api/routes/documents.py

**Checkpoint**: All three search types return relevant results. Hybrid search combines text+semantic via RRF.

---

## Phase 8: User Story 7 — Job Management (Priority: P2)

**Goal**: Users can list/cancel/retry jobs, view Prefect task progress and logs, and receive webhook callbacks on job completion.

**Independent Test**: Trigger a job, cancel it (verify CANCELLED), trigger a failing job, retry it (verify resumes from last task), configure callback_url and verify webhook delivery.

**Depends on**: US1 (requires jobs to manage)

- [ ] T071 [US7] Implement job cancellation: POST /jobs/{id}/cancel — validate job is PENDING or RUNNING, cancel via Prefect API (cancel flow run by prefect_flow_run_id) for RUNNING jobs; for PENDING jobs with null prefect_flow_run_id, update status directly to CANCELLED in database, return 409 for non-cancellable states per openapi.yaml in src/api/routes/jobs.py
- [ ] T072 [US7] Implement job retry: POST /jobs/{id}/retry — validate job is FAILED (only retryable state, COMPLETED and CANCELLED are terminal), reset status to PENDING, trigger new Prefect flow run, return 409 for non-FAILED states per openapi.yaml in src/api/routes/jobs.py
- [ ] T073 [US7] Implement job listing and detail routes: GET /jobs (list with repository_id/status/branch query filters and cursor pagination), GET /jobs/{id}/tasks (query Prefect API for task run states by flow_run_id), GET /jobs/{id}/logs (query Prefect API for flow run logs) per openapi.yaml in src/api/routes/jobs.py
- [ ] T074 [US7] Implement callback_url webhook notification: create deliver_callback Prefect task that POSTs WebhookPayload (job_id, status, repository_id, branch, pull_request_url, quality_report, token_usage, error_message, completed_at per openapi.yaml) to callback_url with 3 retries and exponential backoff (2s, 4s, 8s base) on transient failures via httpx in src/flows/tasks/callback.py
- [ ] T075 [US7] Implement reconcile_stale_jobs: query jobs with RUNNING status, check corresponding Prefect flow run states via Prefect API, update mismatched jobs to FAILED with error_message "Stale job reconciled on startup", call during FastAPI lifespan startup in src/flows/tasks/reconcile.py
- [ ] T075b [P] [US7] Implement scheduled orphan temp dir cleanup: Prefect scheduled deployment (every 15 minutes) that scans for and removes autodoc_* temp directories older than 1 hour, log cleanup results in src/flows/tasks/cleanup.py (extend existing cleanup module) (primarily for local dev; in K8s production, ephemeral pod volumes handle cleanup automatically). Add deployment definitions to prefect.yaml: dev-cleanup (local-dev pool, scheduled every 15 min), prod-cleanup (k8s-pool, scheduled every 15 min)

**Checkpoint**: Job lifecycle (create, cancel, retry, list, status, tasks, logs, callbacks) fully operational

---

## Phase 9: User Story 8 — Webhook-Driven Documentation Updates (Priority: P3)

**Goal**: Git provider push webhooks automatically trigger documentation generation jobs.

**Independent Test**: Send simulated GitHub push webhook to POST /webhooks/push for a registered repository on a configured branch. Verify job is triggered (202). Send for unregistered repo or non-configured branch — verify 204 skip.

**Depends on**: US1 (requires registered repositories and job creation)

- [ ] T076 [US8] Implement webhook receiver: POST /webhooks/push — detect provider from headers (X-GitHub-Event for GitHub, X-Event-Key for Bitbucket), parse provider-specific payload to extract repo URL + branch + commit_sha, look up repository by URL via RepositoryRepo, return 204 if not registered or branch not in branch_mappings, auto-determine full/incremental, create job via existing POST /jobs logic (inherits idempotency for rapid successive pushes), return 202 with job_id per openapi.yaml in src/api/routes/webhooks.py
- [ ] T077 [US8] Implement provider-specific webhook payload parsers as helper functions: parse_github_push (repository.clone_url, ref→branch via refs/heads/ strip, after→commit_sha) and parse_bitbucket_push (repository.links.html.href, push.changes[0].new.name→branch, push.changes[0].new.target.hash→commit_sha) in src/api/routes/webhooks.py

**Checkpoint**: Push webhooks from GitHub and Bitbucket trigger appropriate documentation jobs

---

## Phase 10: User Story 9 — MCP Server for External Agents (Priority: P3)

**Goal**: External AI agents can discover repositories and search documentation via two MCP tools.

**Independent Test**: Connect MCP client to autodoc MCP server, call find_repository with a search term, then call query_documents with returned repository to search documentation.

**Depends on**: US1 (repositories), US6 (search capability)

- [ ] T078 [US9] Implement FastMCP server: find_repository tool (search repos by name/URL/partial match via RepositoryRepo, return id/name/provider/branches), query_documents tool (accept repository_id, delegate to search service for hybrid search, return ranked pages with snippets), use database engine and repos from src/database/ in src/mcp_server.py

**Checkpoint**: MCP client can discover repositories and query their documentation

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Production deployment infrastructure and end-to-end validation

- [ ] T079 [P] Create Dockerfile.api: python:3.11-slim base, uv install production deps only, copy src/, uvicorn entrypoint on port 8080 in deployment/docker/Dockerfile.api
- [ ] T080 [P] Create Dockerfile.worker: prefecthq/prefect:3-latest base, minimal additional deps, prefect worker start entrypoint in deployment/docker/Dockerfile.worker
- [ ] T081 [P] Create Dockerfile.flow: python:3.11-slim base, Node.js for filesystem MCP server, all AI dependencies (google-adk, litellm, etc.), flow code baked in, APP_COMMIT_SHA build-arg in deployment/docker/Dockerfile.flow
- [ ] T082 Create docker-compose.yml full stack: PostgreSQL/pgvector, Prefect Server, Prefect Worker, API service, with healthchecks, dependency ordering (postgres→prefect-server→worker/api), volume mounts, and environment variable configuration in deployment/docker-compose.yml
- [ ] T083 Validate end-to-end workflow per quickstart.md: register repo → trigger full generation → verify wiki pages stored → search documentation → trigger incremental update → verify selective regeneration → test webhook trigger → validate search queries return within 3 seconds (p95) per SC-004, job management operations within 2 seconds per SC-007
- [ ] T084 [P] Implement agent isolation tests: verify each agent (StructureExtractor, PageGenerator, ReadmeDistiller) is testable via `adk web` in isolation, producing valid AgentResult output with quality scoring, per constitution Development Workflow requirement in tests/integration/test_agents.py
- [ ] T085 [P] Implement flow integration tests: verify full_generation_flow and incremental_update_flow via `prefect_test_harness`, covering happy path, dry-run, force flag, and no-changes short-circuit scenarios per constitution Development Workflow requirement in tests/integration/test_flows.py
- [ ] T086 [P] Implement API integration tests: verify all REST endpoints (repositories CRUD, jobs lifecycle, documents search, webhooks, health) against openapi.yaml contract via pytest with test database per constitution Development Workflow requirement in tests/integration/test_api/ and tests/contract/test_openapi.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1+US3 (Phase 3)**: Depends on Foundational — this is the MVP
- **US2 (Phase 4)**: Depends on US1 (requires stored commit_sha from prior full generation)
- **US4 (Phase 5)**: Depends on US1 (requires working pipeline to test config effects)
- **US5 (Phase 6)**: Depends on US1 + US4 (requires config integration + pipeline)
- **US6 (Phase 7)**: Depends on US1 (requires generated wiki pages to search)
- **US7 (Phase 8)**: Depends on US1 (requires jobs to manage)
- **US8 (Phase 9)**: Depends on US1 (requires registered repositories and job creation)
- **US9 (Phase 10)**: Depends on US1 + US6 (requires repositories and search)
- **Polish (Phase 11)**: Depends on all user stories

### User Story Dependency Graph

```
Phase 1 (Setup) → Phase 2 (Foundational)
                        ↓
                   Phase 3 (US1+US3) ← MVP
                  / |    |    |    \
                 ↓  ↓    ↓    ↓    ↓
               US2 US4  US6  US7  US8    ← Can run in parallel
                    ↓         ↓
                   US5       US9
                        ↓
                      Polish
```

### Within Each User Story

- Schemas/interfaces before implementations
- Services before flow tasks
- Flow tasks before flows
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T006, T007, T008 in parallel (independent config modules)
- T011–T015 in parallel (independent ORM model files)
- T017–T019 in parallel (independent repo classes)

**Phase 3 (US1+US3)**:
- T025, T026 in parallel (independent API schema files)
- T029, T030 in parallel (independent provider implementations)
- T032, T033 in parallel (independent dataclass files)
- T040, T041 in parallel (independent flow tasks with no cross-dependencies)
- T046–T049 in parallel (independent flow tasks)

**After Phase 3 (US1)**:
- US2, US4, US6, US7, US8 can ALL start in parallel (independent concerns, different files)
- US5 starts after US4 completes
- US9 starts after US6 completes

---

## Parallel Example: Phase 3 (US1+US3)

```
# Wave 1 — API schemas + provider interface + agent infrastructure (parallel):
Task T025: "Repository API schemas and routes"
Task T026: "Job API schemas"
Task T028: "GitProvider interface"
Task T031: "BaseAgent interface"
Task T032: "AgentResult dataclass"
Task T033: "EvaluationResult dataclass"

# Wave 2 — implementations depending on Wave 1 (parallel where marked):
Task T027: "Job routes" (needs T026)
Task T029: "[P] GitHubProvider" (needs T028)
Task T030: "[P] BitbucketProvider" (needs T028)
Task T034: "LoopAgent wrapper" (needs T032, T033)
Task T035: "Filesystem MCP toolset" (independent)

# Wave 3 — agents + services (after Wave 2):
Task T036: "StructureExtractor" (needs T034, T035)
Task T037: "PageGenerator" (needs T034, T035)
Task T038: "ReadmeDistiller" (needs T034)
Task T039: "Config loader" (independent)

# Wave 4 — flow tasks (after Wave 3, many parallel):
Tasks T040–T049: Flow tasks (parallel where marked [P])

# Wave 5 — flows (after Wave 4):
Task T050: "scope_processing_flow"
Task T051: "full_generation_flow" (needs T050)
Task T052: "prefect.yaml"
```

---

## Implementation Strategy

### MVP First (US1 + US3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: US1+US3 (Full Generation + Quality Gating)
4. **STOP and VALIDATE**: Register a repo → trigger job → verify wiki pages + README PR
5. Deploy/demo the MVP

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1+US3 → Full generation pipeline works → **MVP!**
3. US2 → Incremental updates work (practical for ongoing use)
4. US4 + US6 + US7 + US8 → In parallel: config customization + search + job management + webhooks
5. US5 → Monorepo support (after US4)
6. US9 → MCP server (after US6)
7. Polish → Production-ready deployment

### Parallel Team Strategy

With multiple developers after Foundational:

1. Team completes Setup + Foundational together
2. Team completes US1+US3 together (tightly interconnected)
3. Once US1 is done:
   - Developer A: US2 (incremental) → US8 (webhooks)
   - Developer B: US6 (search) → US9 (MCP)
   - Developer C: US4 (config) → US5 (monorepo)
   - Developer D: US7 (job management)
4. All developers: Polish phase

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks within the same phase
- [Story] label maps task to specific user story for traceability
- US3 is embedded in US1 — the Generator & Critic loop IS how all agents work
- Each user story after US1 is independently testable given US1 completion
- All database writes within Prefect @task boundaries (atomic commit per task)
- OpenTelemetry TracerProvider MUST be configured before any ADK imports (critical ordering in main.py)
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
