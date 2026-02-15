<!--
## Sync Impact Report
- **Version change**: 1.0.0 → 1.1.0 (MINOR — new constraints added,
  no existing principles changed)
- **Modified principles**: None
- **Added sections**:
  - Technology & Infrastructure Constraints: Ephemeral Workspaces,
    Git Providers (GitHub + Bitbucket only), Provider Abstraction
  - Development Workflow & Quality Gates: Job Idempotency
- **Removed sections**: None
- **Templates requiring updates**:
  - `.specify/templates/plan-template.md` — ✅ No changes needed
    (Constitution Check section is generic, populated at plan time)
  - `.specify/templates/spec-template.md` — ✅ No changes needed
    (FR/NFR format is compatible)
  - `.specify/templates/tasks-template.md` — ✅ No changes needed
    (Phase-based structure is compatible)
- **Follow-up TODOs**:
  - ⚠ `specs/001-autodoc-adk-docgen/spec.md` references GitLab in
    FR-001, SC-006, Key Entities (Repository), and Assumptions.
    These MUST be updated to reflect GitHub + Bitbucket only.
  - ⚠ `specs/001-autodoc-adk-docgen/spec.md` FR-016 requires S3
    session archival. This MUST be replaced with ephemeral workspace
    cleanup semantics (no S3 dependency).
-->

# AutoDoc ADK Constitution

## Core Principles

### I. Agent Isolation

All ADK-specific code MUST be confined within each agent module's
boundary (`src/agents/{agent_name}/`). Agents MUST implement the
common `BaseAgent` interface with a single
`async run(input) -> AgentResult[output]` method. Workflow tasks,
services, and API routes MUST depend only on `BaseAgent` — never on
ADK types directly.

**Rationale**: Decouples orchestration from the LLM framework, making
agents swappable (ADK today, raw API or another framework tomorrow)
without touching workflow or API code.

### II. Generator & Critic Separation

Every generating agent (StructureExtractor, PageGenerator,
ReadmeDistiller) MUST pair a Generator sub-agent with a separate
Critic sub-agent (LLM-as-Judge). The Critic MUST evaluate against a
weighted rubric with per-criterion scores. Generator and Critic MUST
support independent model configuration via environment variables
(e.g., `PAGE_GENERATOR_MODEL` vs `PAGE_CRITIC_MODEL`).

**Rationale**: Using the same model to generate and self-evaluate
creates self-reinforcing bias. Separate models and structured rubrics
produce more honest quality assessments.

### III. Quality-Gated Output (NON-NEGOTIABLE)

All agent output MUST pass through the Generator & Critic loop before
being accepted. Output below `MINIMUM_SCORE_FLOOR` MUST cause the job
to be marked `FAILED`. Per-criterion minimum floors (e.g., accuracy
>= 5.0) MUST be enforced alongside the overall threshold to prevent
masking critical failures. The best attempt (highest score) — not the
last attempt — MUST be tracked and returned.

**Rationale**: Documentation quality is the product's core value
proposition. Shipping low-quality output erodes user trust more than
failing visibly.

### IV. Prefect-First Orchestration

All workflow coordination MUST use Prefect flows and tasks. Each
Prefect task MUST be the unit of transactional consistency (one task =
one atomic DB commit). Cross-task consistency MUST be managed by
flow-level retry and error handling. Custom orchestration logic
outside of Prefect MUST NOT be introduced. The Prefect UI MUST serve
as the primary ops dashboard.

**Rationale**: Prefect provides battle-tested retry, state management,
concurrency control, and observability. Duplicating these in
application code creates maintenance burden and reliability gaps.

### V. Concrete Data Layer

PostgreSQL + pgvector MUST be the single database. There MUST be no
abstract repository interfaces or repository pattern indirection.
Database repositories MUST be concrete classes using SQLAlchemy async
with asyncpg. FastAPI `Depends()` MUST be the sole dependency
injection mechanism for services and repositories.

**Rationale**: The system has one storage backend. Abstracting over a
single implementation adds complexity without benefit and obscures the
actual data access patterns.

### VI. Structured Error Hierarchy

All application exceptions MUST extend the three-tier hierarchy:
`TransientError` (retryable — rate limits, timeouts),
`PermanentError` (non-retryable — invalid config, missing repo), and
`QualityError` (agent loop handles internally). Prefect retry logic
MUST key off error type. New exception classes MUST extend one of
these three tiers.

**Rationale**: Intelligent retry behavior requires the system to
distinguish between errors that may resolve on retry and errors that
never will. Catching generic `Exception` leads to wasted retries or
missed recovery opportunities.

### VII. Observability by Design

All log entries MUST be JSON-structured and MUST include `job_id`,
`agent_name`, and `task_name` correlation fields. OpenTelemetry
`TracerProvider` MUST be configured before any ADK imports.
`LoggingInstrumentor` MUST inject `trace_id` and `span_id` into all
log records. Token usage and quality metrics MUST be carried in
`AgentResult` and aggregated via `aggregate_job_metrics()` — no
in-process span storage.

**Rationale**: A multi-agent system with retry loops is difficult to
debug without structured, correlated telemetry. Metrics carried in
domain objects (not span storage) keep the architecture simple while
preserving full visibility.

## Technology & Infrastructure Constraints

- **Language**: Python 3.11+
- **AI Framework**: Google ADK with `DatabaseSessionService` for
  session persistence
- **Orchestration**: Prefect 3 (work pools, not agents)
- **Database**: PostgreSQL 18+ with pgvector extension
- **ORM**: SQLAlchemy async + asyncpg
- **API**: FastAPI with async endpoints
- **Git Providers**: GitHub and Bitbucket only. Provider-specific
  code (cloning, diff detection, PR creation) MUST be isolated
  behind a common `GitProvider` interface with one concrete
  implementation per provider. Workflow and agent code MUST depend
  only on the `GitProvider` interface — never on provider-specific
  clients directly
- **Ephemeral Workspaces**: Each job MUST clone repositories into a
  temporary directory scoped to that job. The workspace MUST be
  deleted when the job completes (success or failure). ADK sessions
  MUST be cleaned up from PostgreSQL after flow completion. No
  external object storage (S3 or equivalent) is required. A
  scheduled cleanup task MUST remove orphaned `autodoc_*` temp
  directories older than 1 hour to handle crashed workers
- **Deployment**: Three Docker images (API, Worker, Flow Runner);
  Kubernetes in production, process work pool for local dev
- **Configuration**: Pydantic `BaseSettings` for env var management;
  `.autodoc.yaml` for per-scope repo configuration with strict
  validation
- **Authentication**: Deferred to deployment infrastructure (reverse
  proxy / API gateway). The application MUST NOT implement its own
  auth middleware
- **Rate Limiting**: Handled at reverse proxy layer (NGINX / cloud
  LB). The application MUST NOT implement rate limiting
- **Pagination**: All list endpoints MUST use cursor-based pagination

## Development Workflow & Quality Gates

- **Agent testing**: Individual agents MUST be testable via
  `adk web` in isolation. Integration tests MUST verify the full
  Generator & Critic loop produces valid `AgentResult` output
- **Flow testing**: Prefect flows MUST be testable via
  `prefect_test_harness`. Integration tests MUST cover both full and
  incremental flow paths
- **API testing**: All API endpoints MUST have integration tests via
  pytest with test database
- **Transaction discipline**: Database writes MUST occur within
  Prefect task boundaries. No writes outside of task context
- **Job idempotency**: Duplicate job requests for the same
  `(repository_id, branch, dry_run)` MUST return the existing active
  job instead of creating a new one. This MUST be enforced at the
  database level (unique partial index on active jobs) to prevent
  race conditions
- **Config validation**: `.autodoc.yaml` parsing MUST warn on unknown
  keys and fail on invalid values. Validation results MUST be stored
  in the job record
- **Repo size enforcement**: `MAX_TOTAL_FILES`, `MAX_FILE_SIZE`, and
  `MAX_REPO_SIZE` MUST be enforced during `scan_file_tree`
- **Version retention**: Wiki structures MUST retain at most 3
  versions per `(repository_id, branch, scope_path)`. Deletion of
  older versions MUST cascade to pages and embeddings via FK

## Governance

This constitution is the authoritative source for architectural
decisions and non-negotiable constraints. All implementation work
MUST verify compliance with these principles. Amendments require:

1. A written proposal describing the change and its rationale
2. An impact analysis identifying affected code, templates, and docs
3. A version bump following semantic versioning (MAJOR for principle
   removal/redefinition, MINOR for additions, PATCH for wording)
4. Update of all dependent artifacts listed in the Sync Impact Report

Complexity beyond what these principles prescribe MUST be explicitly
justified in the relevant plan or spec document.

**Version**: 1.1.0 | **Ratified**: 2026-02-15 | **Last Amended**: 2026-02-15
