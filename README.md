# AutoDoc ADK

AI-powered documentation generator that analyzes codebases and produces wiki-style documentation with quality-gated agents, semantic search, and automated pull requests.

Built with [Google ADK](https://github.com/google/adk-python), [Prefect 3](https://www.prefect.io/), [FastAPI](https://fastapi.tiangolo.com/), and [PostgreSQL/pgvector](https://github.com/pgvector/pgvector).

## Table of Contents

- [How It Works](#how-it-works)
- [Features](#features)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Search](#search)
- [MCP Server](#mcp-server)
- [Architecture](#architecture)
- [Deployment](#deployment)
- [Development](#development)
- [Testing](#testing)
- [Tech Stack](#tech-stack)
- [License](#license)

## How It Works

AutoDoc registers Git repositories, clones them, and runs three AI agents to produce documentation:

1. **StructureExtractor** reads the repository through a filesystem MCP server and generates a wiki structure (sections, subsections, page specifications).
2. **PageGenerator** reads source files for each page specification and writes detailed markdown documentation.
3. **ReadmeDistiller** condenses the generated wiki pages into a distilled README.

Each agent uses a **Generator + Critic loop**: a Generator LlmAgent produces content, then a separate Critic LlmAgent evaluates it against a weighted rubric (accuracy, completeness, clarity). If the score falls below a configurable threshold, the Critic's feedback feeds back to the Generator for another attempt (up to 3 by default). The best-scoring attempt is kept.

```mermaid
flowchart TD
    A[Register Repo] --> B[Clone]
    B --> C[Scan Files]
    C --> D[Extract Structure<br><i>Generator + Critic</i>]

    D --> E1[Generate Page 1<br><i>Generator + Critic</i>]
    D --> E2[Generate Page 2<br><i>Generator + Critic</i>]
    D --> E3[Generate Page N<br><i>Generator + Critic</i>]

    E1 & E2 & E3 --> F1[Distill README<br><i>Generator + Critic</i>]
    E1 & E2 & E3 --> F2[Generate Embeddings<br><i>chunk + vectorize</i>]

    F1 & F2 --> G[Close Stale PRs]
    G --> H[Create PR]
    H --> I[Archive Sessions]
    I --> J[Cleanup Workspace]
```

Each agent's Generator + Critic loop:

```mermaid
flowchart LR
    G[Generator LLM] -->|produces content| C[Critic LLM]
    C -->|score >= threshold| Pass[Accept Best Attempt]
    C -->|score < threshold| G
    C -.->|max attempts reached| Pass
```

After initial generation, subsequent runs auto-detect changes via the provider's compare API and regenerate only affected pages (incremental mode).

## Features

**Documentation Generation**
- Full and incremental generation modes (auto-detected based on existing documentation)
- Quality-gated output: Generator + Critic loop with configurable score thresholds (default 7.0/10) and per-criterion minimum floors
- Dry-run mode for structure-only extraction without content generation
- Automated PR creation with configurable reviewers and auto-merge

**Repository Support**
- GitHub and Bitbucket (clone, compare, pull requests)
- Private repositories via access tokens
- Monorepo support with multiple `.autodoc.yaml` scopes processed in parallel
- Repository size limits enforced (500 MB, 5000 files, 1 MB per file)

**Search**
- Full-text search via PostgreSQL GIN indexes
- Semantic search via pgvector cosine similarity on 3072-dimensional embeddings
- Hybrid search combining both via Reciprocal Rank Fusion (RRF, k=60)
- Chunk-based embeddings (512 tokens, 50-token overlap) with best-chunk-wins page aggregation

**Job Management**
- Cancel pending or running jobs via Prefect native cancellation
- Retry failed jobs
- Webhook callbacks on job completion or failure (3 retries, exponential backoff)
- Job idempotency: duplicate requests return the existing active job
- 1-hour hard timeout per job

**Operations**
- Prefect UI as primary operations dashboard
- REST API for programmatic access (15 endpoints)
- OpenTelemetry tracing with structured JSON logging (trace_id, span_id, job_id correlation)
- Stale job reconciliation on startup
- Scheduled cleanup of orphaned workspaces (every 15 minutes)

**Extensibility**
- MCP server with `find_repository` and `query_documents` tools for external AI agents
- Multi-provider LLM support: Gemini (native), Vertex AI, Azure OpenAI, AWS Bedrock via LiteLLM
- Per-agent model overrides (Generator and Critic can use different models)
- Webhook-driven updates from GitHub/Bitbucket push events

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker and Docker Compose
- Git
- Node.js 18+ (required for the filesystem MCP server used by agents)

### Option A: Full Docker Stack

```bash
git clone <repo-url> autodoc-adk && cd autodoc-adk
cp .env.example .env
# Edit .env with your LLM provider credentials

cd deployment
make dev-up       # Start PostgreSQL + Prefect Server
make migrate      # Run database migrations
make deploy-local # Deploy Prefect flows
make worker       # Start Prefect worker (new terminal)
make api          # Start FastAPI server (new terminal)
```

Services start at:
- **API**: http://localhost:8080
- **Prefect UI**: http://localhost:4200
- **PostgreSQL**: localhost:5432

### Option B: Full Docker Compose

```bash
cd deployment
docker compose up
```

This starts PostgreSQL (pgvector), Prefect Server, Prefect Worker, and the API together.

### Basic Usage

**1. Register a repository**

```bash
curl -X POST http://localhost:8080/repositories \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://github.com/your-org/your-repo",
    "provider": "github",
    "branch_mappings": {"main": "main"},
    "public_branch": "main"
  }'
```

**2. Trigger documentation generation**

```bash
curl -X POST http://localhost:8080/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "repository_id": "<repository-id-from-step-1>"
  }'
# Mode (full/incremental) is auto-determined.
# Add "force": true for full regeneration.
# Add "dry_run": true for structure-only extraction.
```

**3. Check job status**

```bash
curl http://localhost:8080/jobs/<job-id>
```

**4. Search documentation**

```bash
# Hybrid search (recommended)
curl "http://localhost:8080/documents/<repo-id>/search?query=authentication&search_type=hybrid"

# Text search
curl "http://localhost:8080/documents/<repo-id>/search?query=authentication&search_type=text"

# Semantic search
curl "http://localhost:8080/documents/<repo-id>/search?query=how+does+auth+work&search_type=semantic"
```

**5. Browse generated documentation**

```bash
# List wiki structure
curl "http://localhost:8080/documents/<repo-id>"

# Read a specific page
curl "http://localhost:8080/documents/<repo-id>/pages/<page-key>"

# List scopes (monorepo)
curl "http://localhost:8080/documents/<repo-id>/scopes"
```

## Configuration

### Environment Variables

Core settings in `.env` (see `.env.example` for the full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://autodoc:autodoc@localhost:5432/autodoc` | PostgreSQL connection |
| `PREFECT_API_URL` | `http://localhost:4200/api` | Prefect Server endpoint |
| `PREFECT_WORK_POOL` | `local-dev` | Work pool name |
| `DEFAULT_MODEL` | `gemini-2.5-flash` | Default LLM model |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding model |
| `EMBEDDING_DIMENSIONS` | `3072` | Embedding vector dimensions |
| `QUALITY_THRESHOLD` | `7.0` | Minimum quality score (1-10 scale) |
| `MAX_AGENT_ATTEMPTS` | `3` | Max Generator-Critic iterations |

**Per-agent model overrides** (Critic can differ from Generator to avoid self-reinforcing bias):

| Variable | Description |
|----------|-------------|
| `STRUCTURE_GENERATOR_MODEL` | Structure extraction model |
| `STRUCTURE_CRITIC_MODEL` | Structure evaluation model |
| `PAGE_GENERATOR_MODEL` | Page content model |
| `PAGE_CRITIC_MODEL` | Page evaluation model |
| `README_GENERATOR_MODEL` | README distillation model |
| `README_CRITIC_MODEL` | README evaluation model |

Models use provider-prefixed strings: `gemini-*` (native), `vertex_ai/*`, `azure/*`, `bedrock/*`.

**Per-criterion quality floors** (prevent masking critical failures behind a high average):

| Variable | Default | Description |
|----------|---------|-------------|
| `STRUCTURE_COVERAGE_CRITERION_FLOOR` | `5.0` | Minimum structure coverage score |
| `PAGE_ACCURACY_CRITERION_FLOOR` | `5.0` | Minimum page accuracy score |

### Repository Configuration (.autodoc.yaml)

Place a `.autodoc.yaml` file in your repository to customize documentation generation. For monorepos, place one in each scope directory.

```yaml
version: "1"

# File inclusion/exclusion (empty include = all files)
include:
  - src/
  - lib/
exclude:
  - "*.test.*"
  - __pycache__/

# Documentation style
style:
  audience: "senior-developer"    # Target reader
  tone: "technical"               # Writing tone
  detail_level: "comprehensive"   # minimal | standard | comprehensive

# Free-form instructions injected into agent prompts
custom_instructions: |
  DPU stands for "Data Processing Unit".
  Always document error handling patterns.

# README preferences
readme:
  output_path: "README.md"   # Relative to this file's directory
  max_length: null            # Word cap (null = unlimited)
  include_toc: true
  include_badges: true

# Pull request settings
pull_request:
  auto_merge: false
  reviewers: ["@team-leads"]
```

**Monorepo behavior**: AutoDoc discovers all `.autodoc.yaml` files in the repository. Each defines a documentation scope processed independently. Parent scopes auto-exclude directories that contain their own `.autodoc.yaml`.

## API Reference

### Repositories

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/repositories` | Register a repository |
| GET | `/repositories` | List repositories (cursor pagination) |
| GET | `/repositories/{id}` | Get repository details |
| PATCH | `/repositories/{id}` | Update repository settings |
| DELETE | `/repositories/{id}` | Delete repository (cascades to all docs) |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jobs` | Trigger documentation generation |
| GET | `/jobs` | List jobs (filter by repo, status, branch) |
| GET | `/jobs/{id}` | Get job status and results |
| GET | `/jobs/{id}/structure` | Get extracted wiki structure |
| GET | `/jobs/{id}/tasks` | Get Prefect task states |
| GET | `/jobs/{id}/logs` | Get Prefect flow run logs |
| POST | `/jobs/{id}/cancel` | Cancel a pending or running job |
| POST | `/jobs/{id}/retry` | Retry a failed job |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/documents/{repo_id}` | Get wiki structure (cursor pagination) |
| GET | `/documents/{repo_id}/pages/{page_key}` | Get full page content |
| GET | `/documents/{repo_id}/search` | Search documentation |
| GET | `/documents/{repo_id}/scopes` | List documentation scopes |

All document endpoints accept `?branch=` and `?scope=` query parameters.

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhooks/push` | Git provider push webhook receiver |
| GET | `/health` | Health check (database, Prefect, OpenTelemetry) |

Full OpenAPI specification: [`specs/001-autodoc-adk-docgen/contracts/openapi.yaml`](specs/001-autodoc-adk-docgen/contracts/openapi.yaml)

## Search

AutoDoc supports three search modes on generated documentation:

**Text search** uses PostgreSQL full-text indexing (`tsvector` + GIN index) for keyword matching. Fast and precise for exact terms.

**Semantic search** embeds the query with the same model used for document chunks (default: `text-embedding-3-large`, 3072 dimensions) and finds similar chunks via pgvector cosine similarity. Pages rank by their highest-scoring chunk (best-chunk-wins aggregation).

**Hybrid search** (recommended) combines both approaches using Reciprocal Rank Fusion (RRF) with k=60. Each result's score is `1/(60 + text_rank) + 1/(60 + semantic_rank)`. Pages absent from one ranking receive a penalty rank of 1000. This balances keyword precision with semantic understanding.

### Chunking Strategy

Page content splits into chunks for embedding:

1. **Heading-aware split**: divide on markdown headings (never inside fenced code blocks or tables)
2. **Recursive fallback**: sections exceeding 512 tokens split further at paragraph, sentence, then word boundaries with 50-token overlap

Each chunk tracks its heading path, heading level, token count, character offsets, and whether it contains code.

## MCP Server

AutoDoc exposes an MCP server for external AI agents using [FastMCP](https://github.com/jlowin/fastmcp). Two tools are available:

**`find_repository`** — Search registered repositories by name, URL, or organization. Returns repository IDs, names, providers, and configured branches.

**`query_documents`** — Search documentation for a given repository. Accepts a natural language query and returns ranked pages with snippets, scores, and chunk-level context. Defaults to hybrid search.

## Architecture

### Project Structure

```
src/
├── main.py                     # Entry point (telemetry → FastAPI)
├── errors.py                   # TransientError, PermanentError, QualityError
├── mcp_server.py               # FastMCP server (find_repository, query_documents)
├── config/                     # Settings, model factory, telemetry
├── agents/
│   ├── base.py                 # BaseAgent interface
│   ├── common/                 # AgentResult, EvaluationResult, quality loop, MCP tools
│   ├── structure_extractor/    # Repository structure analysis agent
│   ├── page_generator/         # Documentation page generation agent
│   └── readme_distiller/       # README distillation agent
├── api/
│   ├── app.py                  # FastAPI app factory + lifespan
│   ├── routes/                 # repositories, jobs, documents, webhooks, health
│   └── schemas/                # Pydantic request/response models
├── database/
│   ├── engine.py               # Async SQLAlchemy engine + session factory
│   ├── models/                 # Repository, Job, WikiStructure, WikiPage, PageChunk
│   ├── repos/                  # RepositoryRepo, JobRepo, WikiRepo, SearchRepo
│   └── migrations/             # Alembic async migrations
├── flows/
│   ├── full_generation.py      # Full documentation generation orchestrator
│   ├── incremental_update.py   # Incremental update orchestrator
│   ├── scope_processing.py     # Per-scope worker flow
│   └── tasks/                  # 14 Prefect tasks (clone, scan, structure, pages, ...)
├── providers/
│   ├── base.py                 # GitProvider interface
│   ├── github.py               # GitHub (clone, compare, PR, webhooks)
│   └── bitbucket.py            # Bitbucket (clone, compare, PR, webhooks)
└── services/
    ├── chunking.py             # Heading-aware markdown chunking
    ├── embedding.py            # Batch embedding generation
    ├── search.py               # Search orchestrator (text, semantic, hybrid)
    └── config_loader.py        # .autodoc.yaml parsing + validation
```

### Data Model

```mermaid
erDiagram
    Repository ||--o{ Job : triggers
    Repository ||--o{ WikiStructure : contains
    WikiStructure ||--o{ WikiPage : contains
    WikiPage ||--o{ PageChunk : splits_into

    Repository {
        uuid id PK
        string provider "github | bitbucket"
        string url UK
        string org
        string name
        jsonb branch_mappings
        string public_branch
    }

    Job {
        uuid id PK
        uuid repository_id FK
        string status "PENDING | RUNNING | COMPLETED | FAILED | CANCELLED"
        string mode "full | incremental"
        string branch
        string commit_sha
        jsonb quality_report
        jsonb token_usage
        string callback_url
        string pull_request_url
    }

    WikiStructure {
        uuid id PK
        uuid repository_id FK
        string branch
        string scope_path
        int version "max 3 retained"
        jsonb sections
        string commit_sha
    }

    WikiPage {
        uuid id PK
        uuid wiki_structure_id FK
        string page_key UK
        string title
        text content "GIN index"
        float quality_score
        jsonb source_files
    }

    PageChunk {
        uuid id PK
        uuid wiki_page_id FK
        int chunk_index
        text content
        vector content_embedding "HNSW index, 3072 dim"
        int token_count "512 target"
    }
```

### Error Hierarchy

| Error Type | Behavior | HTTP Status |
|------------|----------|-------------|
| `TransientError` | Retryable (rate limits, timeouts, network issues) | 503 |
| `PermanentError` | Fail fast (invalid config, missing repo, validation) | 400 |
| `QualityError` | Handled by agent loop and flow error handlers | 422 |

### Flow Orchestration

Prefect 3 orchestrates all workflows. Each Prefect task is an atomic database transaction.

**Full generation flow**:

```mermaid
flowchart LR
    A[Clone] --> B[Scan]
    B --> C[Discover Configs]
    C --> D[Process Scopes<br><i>parallel</i>]
    D --> E[Close Stale PRs]
    E --> F[Create PR]
    F --> G[Aggregate Metrics]
    G --> H[Archive Sessions]
    H --> I[Cleanup]
```

**Incremental update flow**:

```mermaid
flowchart LR
    A[Resolve<br>Baseline SHA] --> B[Compare Commits<br><i>provider API</i>]
    B --> C{Structural<br>Changes?}
    C -->|yes| D[Re-extract<br>Structure]
    C -->|no| E[Reuse<br>Structure]
    D & E --> F[Regenerate<br>Affected Pages]
    F --> G[Duplicate<br>Unchanged Pages]
    G --> H[Create PR]
```

**Scope processing flow**:

```mermaid
flowchart LR
    A[Scan File Tree] --> B[Extract Structure]
    B --> C[Generate Pages]
    C --> D[Distill README]
    C --> E[Generate Embeddings]
```

### Work Pools

| Pool | Type | Limit | Purpose |
|------|------|-------|---------|
| `local-dev` | Process | — | Local development |
| `orchestrator-pool` | Kubernetes | 10 | Production orchestrator flows |
| `k8s-pool` | Kubernetes | 50 | Production scope workers + cleanup |

## Deployment

### Docker Images

AutoDoc builds three container images:

| Image | Base | Contents | Purpose |
|-------|------|----------|---------|
| **API** | python:3.11-slim | FastAPI + database deps | Serves REST API |
| **Worker** | prefecthq/prefect:3-python3.11 | Prefect worker only | Polls server, launches flow runners |
| **Flow Runner** | python:3.11-slim + Node.js 18 | All AI libs, flow code, git | Executes documentation generation |

### Docker Compose

**Full stack** (`deployment/docker-compose.yml`): PostgreSQL/pgvector, Prefect Server, Worker, API with health checks and dependency ordering.

**Dev infrastructure** (`deployment/docker/docker-compose.dev.yml`): PostgreSQL and Prefect Server only. Run API and Worker locally for hot reload.

### Database

Single PostgreSQL instance hosts two databases:
- `autodoc`: Application data (repositories, jobs, wiki structures, pages, embeddings)
- `prefect`: Prefect Server metadata (auto-managed by Prefect, migrates on startup)

The pgvector extension enables vector similarity search on the `autodoc` database.

### Makefile Targets

Run from the `deployment/` directory:

| Target | Description |
|--------|-------------|
| `make dev-up` | Start dev infrastructure (PostgreSQL + Prefect) |
| `make dev-down` | Stop dev infrastructure |
| `make dev-clean` | Stop and remove all volumes |
| `make migrate` | Run Alembic database migrations |
| `make api` | Start FastAPI dev server (port 8080, hot reload) |
| `make worker` | Start Prefect worker (local-dev pool) |
| `make deploy-local` | Create work pool and deploy all flows |
| `make deploy-flows` | Deploy all Prefect flows |
| `make test` | Run test suite |
| `make lint` | Run ruff linter |

### Webhook Setup

Configure your Git provider to send push events to:

```
POST https://your-host/webhooks/push
```

AutoDoc detects the provider from request headers (`X-GitHub-Event` for GitHub, `X-Event-Key` for Bitbucket), extracts the repository URL and branch, and triggers the appropriate generation job. Unregistered repositories or non-configured branches return 204 (skipped).

## Development

### Setup

```bash
# Install dependencies
uv sync

# Start infrastructure
cd deployment && make dev-up && cd ..

# Run migrations
cd deployment && make migrate && cd ..

# Deploy Prefect flows
cd deployment && make deploy-local && cd ..

# Start worker (terminal 1)
cd deployment && make worker

# Start API with hot reload (terminal 2)
cd deployment && make api
```

### Code Quality

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

Ruff is configured in `pyproject.toml` with rules for pyflakes, pycodestyle, isort, naming, upgrade, bugbear, and simplify. Line length is 120 characters.

### Agent Isolation Testing

Each agent is testable in isolation via the ADK web interface:

```bash
adk web src/agents/structure_extractor
adk web src/agents/page_generator
adk web src/agents/readme_distiller
```

## Testing

```bash
# All tests
cd deployment && make test

# Unit tests only
pytest tests/unit/

# Integration tests (requires PostgreSQL + Prefect)
pytest tests/integration/ -m integration

# Contract tests (API against OpenAPI spec)
pytest tests/contract/
```

Test categories:

| Category | Location | What it covers |
|----------|----------|----------------|
| Unit | `tests/unit/` | Chunking, config loader, errors, schemas, model factory, callbacks, webhooks, search, MCP server |
| Integration | `tests/integration/` | Agent execution, Prefect flows (via `prefect_test_harness`), API endpoints, end-to-end workflows |
| Contract | `tests/contract/` | API responses validated against OpenAPI specification |

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Agents | [Google ADK](https://github.com/google/adk-python) (LlmAgent, LoopAgent, DatabaseSessionService) |
| LLM Providers | Gemini (native), Vertex AI, Azure OpenAI, AWS Bedrock via [LiteLLM](https://github.com/BerriAI/litellm) |
| Orchestration | [Prefect 3](https://www.prefect.io/) (flows, tasks, work pools, deployments) |
| API | [FastAPI](https://fastapi.tiangolo.com/) (async, Pydantic v2) |
| Database | PostgreSQL 18+ with [pgvector](https://github.com/pgvector/pgvector) |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Embeddings | text-embedding-3-large (3072 dimensions) via LiteLLM |
| Observability | OpenTelemetry (TracerProvider + LoggingInstrumentor), structured JSON logs |
| MCP Server | [FastMCP](https://github.com/jlowin/fastmcp) |
| Agent File Access | [@modelcontextprotocol/server-filesystem](https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem) (via Node.js) |
| Package Manager | [uv](https://docs.astral.sh/uv/) |
| Linting | [Ruff](https://docs.astral.sh/ruff/) |
| Testing | pytest + pytest-asyncio, prefect_test_harness |
| Containers | Docker (3 images: API, Worker, Flow Runner) |

## License

MIT
