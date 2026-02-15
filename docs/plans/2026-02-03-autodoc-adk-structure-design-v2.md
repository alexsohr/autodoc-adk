# AutoDoc ADK Project Structure Design (v2)

**Date:** 2026-02-03
**Status:** Approved
**Last Updated:** 2026-02-15 (v2.3 — Prefect deployment patterns: env-specific work pools, deployment switch, dual Docker Compose, Makefile, CI pipeline, webhook receiver, Prefect Server PostgreSQL)
**Supersedes:** v1 (`2026-02-03-autodoc-adk-structure-design.md`)

---

## 1. Overview

A documentation generator built with Google ADK that analyzes codebases and generates comprehensive documentation (API docs, code docs, wiki-style content). Produces two output formats: a structured wiki stored in PostgreSQL for web display and semantic search, and a distilled README.md pushed to the repository via pull request.

### Key Features

| Feature | Approach |
|---------|----------|
| Orchestration | Prefect flows for workflow management, retries, observability |
| Multi-agent | Fan-out: StructureExtractor → parallel PageGenerators → ReadmeDistiller |
| Evaluation | Generator & Critic loop — each agent pairs a Generator sub-agent with a separate Critic (LLM-as-Judge) sub-agent for independent evaluation |
| Telemetry | ADK's built-in OpenTelemetry tracing with LoggingInstrumentor for trace/span ID injection into structured logs; agent metrics aggregated directly from AgentResult |
| Database | PostgreSQL + pgvector for document storage and semantic search |
| MCP | Consume external servers + expose agents as MCP server with text/semantic search |
| API | FastAPI with async job pattern, webhook callbacks, cursor pagination |
| Dual Output | Structured wiki (sections + pages) + distilled README.md via PR |
| Incremental Updates | Provider API-based diff for selective page regeneration with structural diff detection |
| Configuration | Per-scope `.autodoc.yaml` with strict validation for customizing documentation style |
| Monorepo Support | Auto-discovery of `.autodoc.yaml` files — each defines a separate documentation scope with its own wiki and README |
| Testing | ADK WebUI (`adk web`) + pytest for API |

---

## 2. Functional Requirements

- **FR1: Register repositories** — Support public and private repositories across GitHub, Bitbucket, and GitLab. Store repository metadata and encrypted access tokens.
- **FR2: Full documentation generation** — Clone repository, scan and prune the file tree (applying include/exclude patterns and physically removing excluded files), extract documentation structure, generate all pages with quality evaluation, distill README, and create a pull request. End-to-end orchestrated via Prefect.
- **FR3: Incremental documentation updates** — Detect changed files via the provider's API (GitHub/GitLab/Bitbucket compare endpoint), map changes to affected documentation pages, clone with depth=1 only for affected content, scan and prune the file tree, regenerate only affected pages, merge with unchanged pages, re-distill README, and create a PR.
- **FR4: Quality-gated generation** — Each generating agent uses a Generator & Critic loop: a Generator sub-agent produces output, a separate Critic sub-agent (LLM-as-Judge, potentially using a different model) evaluates against weighted criteria, and the loop retries with the Critic's feedback up to a configurable limit. The best attempt is tracked, and results below a minimum quality floor are flagged.
- **FR5: Dual output** — Produce a structured wiki (sections + pages stored in PostgreSQL) for web display and search, plus a distilled README.md that eliminates redundancy into a single cohesive document.
- **FR6: Per-scope configuration** — Support `.autodoc.yaml` files anywhere in the repository. Each `.autodoc.yaml` defines a documentation scope rooted at its directory. A single `.autodoc.yaml` at the repository root covers the entire repo. Multiple `.autodoc.yaml` files enable monorepo support — each sub-project gets its own wiki structure, pages, and README. Customize include/exclude patterns, documentation style, custom instructions, README preferences (including output path), and PR settings per scope.
- **FR10: Monorepo support** — Automatically discover multiple `.autodoc.yaml` files within a repository after cloning. Each file defines an independent documentation scope. The flow fans out per scope: each scope gets its own StructureExtractor, PageGenerators, and ReadmeDistiller. Results are stored with a `scope_path` key. A single job processes all scopes, producing one PR with all scope READMEs.
- **FR7: Search documentation** — Provide text search (PostgreSQL tsvector), semantic search (pgvector), and hybrid search across generated wiki pages via both API and MCP.
- **FR8: PR creation** — Create a pull request containing the generated README.md, with configurable target branch, reviewers, and auto-merge settings.
- **FR9: MCP server** — Expose documentation generation, structure extraction, and documentation search as MCP tools for consumption by external agents.

---

## 3. Non-Functional Requirements

- **NFR1: Concurrency limits** — Enforce configurable limits on concurrent parallel page generation to prevent rate-limit errors.
- **NFR2: Structured logging** — JSON-formatted log entries with correlation IDs (`job_id`), `agent_name`, and `task_name` for machine parseability.
- **NFR3: Token encryption** — Encrypt repository access tokens at rest. Never expose tokens in API responses.
- **NFR4: Temp directory cleanup** — Scheduled cleanup of orphaned `autodoc_*` temp directories older than 1 hour to handle worker crashes.
- **NFR5: Per-agent model configuration** — Each agent (Generator and Critic) can be configured with a different LLM model via environment variables.
- **NFR6: Configurable quality thresholds** — Quality gate thresholds, minimum score floors, and maximum retry attempts are configurable via environment variables.
- **NFR7: Async API** — API endpoints trigger background Prefect flows and return immediately. Job status is queryable via polling or webhook callback.
- **NFR8: Agent telemetry** — All agent execution, LLM calls, and tool usage are traced via ADK's built-in OpenTelemetry integration. `LoggingInstrumentor` injects `trace_id` and `span_id` into structured log entries. Token usage and quality metrics are carried in `AgentResult` and aggregated by the flow.
- **NFR9: Error classification** — All exceptions follow a structured hierarchy: `TransientError` (retryable — rate limits, timeouts), `PermanentError` (non-retryable — invalid config, missing repo), and `QualityError` (agent quality gate failure). Prefect retry logic keys off error type.

---

## 4. System Architecture

### Component Diagram

```mermaid
graph TB
    subgraph "API Layer"
        API[FastAPI Application]
        Routes[Routes: repositories, jobs, documents, webhooks, health]
        Middleware[Middleware: error handling, logging]
    end

    subgraph "Service Layer"
        RepoSvc[RepositoryService]
        JobSvc[JobService]
        WikiSvc[WikiService]
        EmbeddingSvc[EmbeddingService]
    end

    subgraph "Orchestration Layer"
        DocFlow[documentation_flow]
        IncrFlow[incremental_update_flow]
        Tasks[Prefect Tasks: clone, scan tree, extract, generate, distill, embed, PR]
    end

    subgraph "Agent Layer"
        BaseAgent[BaseAgent Interface]
        StructExt[StructureExtractor<br/>Generator + Critic loop]
        PageGen[PageGenerator<br/>Generator + Critic loop]
        ReadmeDist[ReadmeDistiller<br/>Generator + Critic loop]
    end

    subgraph "Telemetry Layer"
        OTel[OpenTelemetry TracerProvider]
        LogInstr[LoggingInstrumentor<br/>trace_id + span_id in logs]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL + pgvector)]
        Repos[repositories table]
        Jobs[jobs table]
        Wiki[wiki_structures + wiki_pages tables]
    end

    subgraph "Provider Layer"
        ProviderBase[ProviderClient Interface]
        GitHub[GitHubProvider]
        GitLab[GitLabProvider]
        Bitbucket[BitbucketProvider]
    end

    subgraph "MCP Layer"
        MCPClients[MCP Clients: filesystem, git]
        MCPServer[MCP Server: generate, search, extract]
    end

    API --> Routes
    Routes --> Middleware
    Routes --> RepoSvc
    Routes --> JobSvc
    Routes --> WikiSvc


    JobSvc --> DocFlow
    JobSvc --> IncrFlow
    DocFlow --> Tasks
    IncrFlow --> Tasks

    Tasks --> StructExt
    Tasks --> PageGen
    Tasks --> ReadmeDist
    StructExt --> BaseAgent
    PageGen --> BaseAgent
    ReadmeDist --> BaseAgent

    StructExt --> MCPClients
    PageGen --> MCPClients

    StructExt --> OTel
    PageGen --> OTel
    ReadmeDist --> OTel
    OTel --> LogInstr

    RepoSvc --> PG
    JobSvc --> PG
    WikiSvc --> PG
    EmbeddingSvc --> PG

    PG --> Repos
    PG --> Jobs
    PG --> Wiki

    Tasks --> ProviderBase
    GitHub --> ProviderBase
    GitLab --> ProviderBase
    Bitbucket --> ProviderBase

    MCPServer --> JobSvc
    MCPServer --> WikiSvc
```

### Architectural Principles

- **Agent isolation** — ADK-specific code never leaks beyond agent module boundaries. All agents implement a common `BaseAgent` interface with a single `run(input) -> AgentResult` method.
- **Generator & Critic separation** — Each generating agent pairs a Generator sub-agent with a separate Critic sub-agent (LLM-as-Judge) using a potentially different model. The Critic evaluates against a weighted rubric and provides structured feedback. This avoids self-reinforcing bias from self-evaluation.
- **Telemetry by design** — ADK's built-in OpenTelemetry integration traces all agent execution, LLM calls, and tool usage automatically. `LoggingInstrumentor` injects `trace_id` and `span_id` into all structured log entries for end-to-end correlation. Token usage and quality metrics are carried in `AgentResult` and aggregated by the flow — no in-process span storage needed.
- **Structured error hierarchy** — All exceptions follow a three-tier hierarchy (`TransientError`, `PermanentError`, `QualityError`) enabling intelligent retry behavior at both the Prefect task level and the agent loop level.
- **Session persistence** — ADK agent sessions are persisted to PostgreSQL via ADK's `DatabaseSessionService`, enabling the Critic's feedback to be fed back to the Generator through the session's conversation history across retry attempts.
- **Transaction scope = Prefect task** — Each Prefect task is the unit of transactional consistency. Database operations within a single task are atomic. Cross-task consistency is managed by the flow's error handling and retry logic.
- **Concrete data layer** — No abstract repository interfaces. PostgreSQL + pgvector is the single database. SQLAlchemy async with asyncpg driver. FastAPI `Depends()` for injection.
- **Prefect orchestration** — Flows coordinate tasks with built-in retry, state management, concurrency control, and observability. No custom orchestration logic. Prefect UI serves as the primary ops dashboard for monitoring flow runs and task states.
- **Single-pod execution model** — Each flow run executes as a single Kubernetes pod. Scope processing uses nested `@flow` subflows (`process_scope`, `process_incremental_scope`) which run **in-process within the parent pod** — they do NOT spawn separate pods. This preserves the single-pod model while providing independent state tracking and error isolation per scope in the Prefect UI. Only `run_deployment()` would create new pods, which is not used here.

---

## 5. Workflow

### Full Documentation Flow

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant Job as JobService
    participant PF as Prefect Flow
    participant Repo as get_repository
    participant Clone as clone_repository
    participant Disc as discover_autodoc_configs
    participant FT as scan_file_tree
    participant SE as StructureExtractor
    participant PG as PageGenerator (parallel)
    participant DB as PostgreSQL
    participant Embed as generate_embeddings
    participant RD as ReadmeDistiller
    participant PR as create_pull_request

    API->>Job: POST /jobs (mode: full)
    Job->>DB: Create job record (PENDING)
    Job->>PF: Trigger documentation_flow(job_id, repository_id, branch)
    Job-->>API: Return job_id

    PF->>Repo: get_repository(repository_id)
    Repo-->>PF: repo (url, name, access_token, ...)

    PF->>Clone: Clone repository
    Clone-->>PF: repo_path, commit_sha

    PF->>Disc: Discover all .autodoc.yaml files
    Note over Disc: Scan repo for .autodoc.yaml<br/>Each defines a documentation scope<br/>Default: [(".", default_config)]
    Disc-->>PF: list of (scope_path, config)

    loop For each scope
        PF->>FT: scan_file_tree(scope_root, config)
        Note over FT: Apply include/exclude patterns<br/>relative to scope root<br/>Generate directory tree
        FT-->>PF: FileTree

        PF->>SE: run(scope_root, file_tree, config)
        Note over SE: Generator + Critic loop<br/>Return best result
        SE-->>PF: AgentResult[PageStructure]

        par For each PageSpec
            PF->>PG: run(page_spec, scope_root, config)
            Note over PG: Generator + Critic loop
            PG-->>PF: AgentResult[GeneratedPage]
        end

        PF->>DB: Store wiki structure + pages (keyed by scope_path)

        par Parallel: Embeddings + README distillation
            PF->>Embed: generate_embeddings(scope pages)
            Embed->>DB: Update wiki_pages.content_embedding
            PF->>RD: run(scope_pages, repo_name, config)
            Note over RD: Generator + Critic loop
            RD-->>PF: AgentResult[ReadmeOutput]
        end

        Note over PF: README not stored in DB —<br/>passed directly to PR creation
    end

    Note over PF: Aggregate token_usage from all<br/>AgentResults (structure + pages + README)

    PF->>PR: Close any existing autodoc PRs for this branch
    PF->>PR: Create branch, commit all scope READMEs, open PR
    PR-->>PF: pr_url

    PF->>DB: Update job (COMPLETED, pr_url, quality_report, token_usage)
    PF->>Job: Fire webhook callback (if configured)
```

### Incremental Update Flow

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant Job as JobService
    participant PF as Prefect Flow
    participant Repo as get_repository
    participant ProvAPI as Provider API
    participant Clone as clone_repository
    participant Cfg as load_autodoc_config
    participant FT as scan_file_tree
    participant DB as PostgreSQL
    participant Diff as diff_changed_files
    participant SDiff as detect_structural_changes
    participant SE as StructureExtractor
    participant Map as map_files_to_pages
    participant PG as PageGenerator (parallel)
    participant Merge as merge_pages
    participant Embed as generate_embeddings
    participant RD as ReadmeDistiller
    participant PR as create_pull_request

    API->>Job: POST /jobs (mode: incremental)
    Job->>DB: Create job record (PENDING)
    Job->>PF: Trigger incremental_update_flow(job_id, repository_id, branch)
    Job-->>API: Return job_id

    PF->>Repo: get_repository(repository_id)
    Repo-->>PF: repo (url, name, access_token, ...)

    PF->>DB: Get previous wiki (commit_sha, pages, branch)
    DB-->>PF: previous state

    Note over PF: baseline_sha = min(commit_sha)<br/>across all previous scopes
    PF->>ProvAPI: Compare baseline_sha..HEAD (GitHub/GitLab/Bitbucket API)
    ProvAPI-->>PF: changed_files

    alt No affected files
        PF->>DB: Update job (no_changes)
    else Has affected files
        PF->>Clone: Clone repository (depth=1, HEAD only)
        Clone-->>PF: repo_path, commit_sha

        PF->>Cfg: Load .autodoc.yaml (strict validation)
        Cfg-->>PF: config (or defaults + warnings)

        PF->>FT: scan_file_tree(repo_path, config)
        Note over FT: Apply include/exclude patterns<br/>Remove excluded files/dirs from clone<br/>Generate directory tree
        FT-->>PF: FileTree

        PF->>SDiff: detect_structural_changes(changed_files, previous.structure)
        Note over SDiff: Check for new top-level dirs,<br/>deleted modules, new file types

        alt structural_change_detected
            PF->>SE: run(repo_path, file_tree, config)
            Note over SE: Re-extract full structure
            SE-->>PF: AgentResult[PageStructure]
            Note over PF: Map all pages from new structure<br/>Mark new pages + changed pages as affected
        else No structural change
            PF->>Map: Cross-reference changed files with page source_files
            Map-->>PF: affected_page_specs
        end
        par For each affected PageSpec
            PF->>PG: run(page_spec, repo_path, config)
            Note over PG: Generator + Critic loop
            PG-->>PF: AgentResult[GeneratedPage]
        end

        PF->>Merge: Combine updated + unchanged pages
        Merge-->>PF: all_pages

        PF->>DB: Store updated wiki structure + pages

        par Parallel: Embeddings + README distillation
            PF->>Embed: generate_embeddings(updated pages)
            Embed->>DB: Update wiki_pages.content_embedding
            PF->>RD: run(all_pages, repo_name, config)
            Note over RD: Generator + Critic loop
            RD-->>PF: AgentResult[ReadmeOutput]
        end

        Note over PF: README passed directly to PR creation

        Note over PF: Aggregate token_usage from<br/>all AgentResults

        PF->>PR: Close any existing autodoc PRs for this branch
        PF->>PR: Create PR with updated README
        PR-->>PF: pr_url
        PF->>DB: Update job (COMPLETED, pr_url, quality_report, token_usage)
        PF->>Job: Fire webhook callback (if configured)
    end
```

### Agent Internal Loop: Generator & Critic Pattern

Each generating agent (StructureExtractor, PageGenerator, ReadmeDistiller) internally runs a Generator & Critic loop. The Generator and Critic are separate ADK sub-agents, potentially using different LLM models to avoid self-reinforcing bias:

```mermaid
sequenceDiagram
    participant Caller as Workflow Task
    participant Ctrl as LoopAgent.run()
    participant Gen as Generator Sub-Agent<br/>(ADK LlmAgent)
    participant Critic as Critic Sub-Agent<br/>(ADK LlmAgent, separate model)
    participant Track as Best Tracker

    Caller->>Ctrl: run(input)

    loop Up to max_attempts (with exponential backoff)
        Ctrl->>Gen: Generate output (with feedback if retry)
        Gen-->>Ctrl: result

        Ctrl->>Critic: Evaluate result against weighted rubric
        Note over Critic: Receives result + rubric criteria<br/>Returns structured scores per criterion
        Critic-->>Ctrl: EvaluationResult (score, passed, feedback)

        Ctrl->>Track: Update best if score > best_score
        Track-->>Ctrl: best_result, best_score

        alt passed = true
            Ctrl-->>Caller: Return AgentResult (passed)
        else passed = false AND more attempts
            Note over Ctrl: Wait backoff_base * 2^(attempt-1)<br/>Feed Critic's feedback to next generation
        end
    end

    alt best_score < MINIMUM_SCORE_FLOOR
        Note over Ctrl: Flag as below quality in AgentResult
    end

    Ctrl-->>Caller: Return AgentResult (best_result)
```

---

## 6. Complete Project Structure

```
autodoc-adk/
│
├── src/
│   ├── __init__.py
│   │
│   ├── agents/                              # ADK Agents
│   │   ├── __init__.py
│   │   │
│   │   ├── shared/                          # Shared agent utilities
│   │   │   ├── __init__.py
│   │   │   ├── base.py                      # BaseAgent interface, AgentResult wrapper
│   │   │   ├── critic.py                    # Critic sub-agent base, rubric schema, EvaluationResult
│   │   │   ├── loop.py                      # Generator & Critic loop controller with backoff
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── filesystem.py
│   │   │   │   ├── repository.py
│   │   │   │   └── documentation.py
│   │   │   └── mcp_toolsets/
│   │   │       ├── __init__.py
│   │   │       ├── filesystem_toolset.py
│   │   │       └── git_toolset.py
│   │   │
│   │   ├── structure_extractor/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py                     # Implements BaseAgent — Generator + Critic loop
│   │   │   ├── prompts.py
│   │   │   ├── tools.py
│   │   │   ├── schemas.py                   # PageStructure, PageSpec, StructureEvaluationResult
│   │   │   └── criteria/                    # Critic rubric definitions (prompt fragments)
│   │   │       ├── __init__.py
│   │   │       ├── coverage.py              # 40% — code area coverage
│   │   │       ├── hierarchy.py             # 30% — logical organization
│   │   │       ├── granularity.py           # 20% — detail level
│   │   │       └── completeness.py          # 10% — mandatory sections
│   │   │
│   │   ├── page_generator/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py                     # Implements BaseAgent — Generator + Critic loop
│   │   │   ├── prompts.py
│   │   │   ├── tools.py
│   │   │   ├── schemas.py                   # GeneratedPage, PageEvaluationResult
│   │   │   ├── templates/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── api.py
│   │   │   │   ├── module.py
│   │   │   │   ├── class.py
│   │   │   │   └── overview.py
│   │   │   └── criteria/                    # Critic rubric definitions (prompt fragments)
│   │   │       ├── __init__.py
│   │   │       ├── accuracy.py              # 35% — code reference correctness
│   │   │       ├── completeness.py          # 25% — element coverage
│   │   │       ├── readability.py           # 20% — clarity and structure
│   │   │       ├── citations.py             # 10% — file reference backing
│   │   │       └── structure.py             # 10% — internal organization
│   │   │
│   │   ├── readme_distiller/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py                     # Implements BaseAgent — Generator + Critic loop
│   │   │   ├── prompts.py
│   │   │   ├── tools.py
│   │   │   ├── schemas.py                   # ReadmeInput, ReadmeOutput, ReadmeEvaluationResult
│   │   │   └── criteria/                    # Critic rubric definitions (prompt fragments)
│   │   │       ├── __init__.py
│   │   │       ├── coherence.py             # 30% — single cohesive document
│   │   │       ├── completeness.py          # 25% — codebase coverage
│   │   │       ├── deduplication.py         # 20% — redundancy elimination
│   │   │       ├── readability.py           # 15% — clarity and audience fit
│   │   │       └── formatting.py            # 10% — markdown quality, TOC, sections
│   │   │
│   │
│   ├── workflows/                           # Prefect Workflow Orchestration
│   │   ├── __init__.py
│   │   │
│   │   ├── flows/
│   │   │   ├── __init__.py
│   │   │   ├── documentation_flow.py        # Full generation flow
│   │   │   └── incremental_flow.py          # Incremental update flow
│   │   │
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── repository.py                # clone_repository, cleanup_repository
│   │   │   ├── config.py                    # discover_autodoc_configs, load_autodoc_config (strict validation)
│   │   │   ├── file_tree.py                 # scan_file_tree (prune excluded files, generate tree)
│   │   │   ├── extraction.py                # extract_structure
│   │   │   ├── generation.py                # generate_page
│   │   │   ├── readme.py                    # distill_readme
│   │   │   ├── embeddings.py                # generate_embeddings
│   │   │   ├── structural_diff.py           # detect_structural_changes, derive_affected_pages
│   │   │   ├── pull_request.py              # create_pull_request, close_stale_autodoc_prs
│   │   │   ├── webhook.py                   # fire_webhook
│   │   │   ├── diff.py                      # diff_changed_files_via_provider (GitHub/GitLab/Bitbucket API)
│   │   │   ├── mapping.py                   # map_files_to_pages
│   │   │   ├── merge.py                     # merge_pages
│   │   │   ├── assembly.py                  # store_wiki, get_previous_documentation
│   │   │   ├── session_archive.py           # archive_adk_sessions (S3 export + cleanup)
│   │   │   ├── maintenance.py               # cleanup_orphaned_repos
│   │   │   └── reconciliation.py           # reconcile_stale_jobs (startup)
│   │   │
│   │   ├── deployments/
│   │   │   ├── __init__.py
│   │   │   └── api_deployment.py
│   │   │
│   │   └── config.py                        # Prefect configuration, concurrency limits
│   │
│   ├── api/                                 # FastAPI
│   │   ├── __init__.py
│   │   ├── main.py                          # create_app() factory
│   │   ├── dependencies.py                  # FastAPI Depends() for repos, services
│   │   │
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── repositories.py
│   │   │   ├── jobs.py                      # Triggers Prefect flows (full or incremental)
│   │   │   ├── documents.py                 # Wiki pages, README, search
│   │   │   └── webhooks.py                  # Git provider push/merge webhook receiver
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── repository.py
│   │   │   ├── job.py
│   │   │   └── document.py
│   │   │
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── error_handler.py
│   │       └── logging.py
│   │
│   ├── domain/                              # Core Business Logic
│   │   ├── __init__.py
│   │   └── entities/
│   │       ├── __init__.py
│   │       ├── repository.py
│   │       ├── job.py
│   │       ├── wiki_structure.py
│   │       ├── wiki_page.py

│   │       └── enums.py                     # JobStatus (incl. CANCELLED), PageImportance, JobMode
│   │
│   ├── database/                            # PostgreSQL + pgvector
│   │   ├── __init__.py
│   │   ├── engine.py                        # AsyncEngine, session factory (pool_size, max_overflow, pool_timeout configurable)
│   │   ├── models.py                        # SQLAlchemy models (JSONB + pgvector)
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── repository_repo.py
│   │   │   ├── job_repo.py
│   │   │   ├── wiki_repo.py                 # WikiStructure + WikiPage repos

│   │   └── migrations/
│   │       ├── env.py
│   │       └── versions/
│   │
│   ├── mcp/                                 # MCP Integration
│   │   ├── __init__.py
│   │   │
│   │   ├── clients/                         # Consuming external MCP servers
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── filesystem_client.py
│   │   │   ├── git_client.py
│   │   │   └── registry.py
│   │   │
│   │   └── servers/                         # Exposed MCP server
│   │       ├── __init__.py
│   │       └── autodoc_server/
│   │           ├── __init__.py
│   │           ├── server.py
│   │           ├── tools/
│   │           │   ├── __init__.py
│   │           │   ├── get_structure.py      # Get wiki structure
│   │           │   └── search_docs.py       # Text + semantic search
│   │           ├── resources/
│   │           │   ├── __init__.py
│   │           │   └── documentation.py
│   │           └── prompts/
│   │               └── templates.py
│   │
│   ├── services/                            # Application Services
│   │   ├── __init__.py
│   │   ├── repository_service.py
│   │   ├── job_service.py                   # Triggers Prefect flows
│   │   ├── wiki_service.py                  # Wiki + page queries and search

│   │   └── embedding_service.py             # Embedding generation for pages
│   │
│   ├── providers/                           # Git Provider Abstraction
│   │   ├── __init__.py
│   │   ├── base.py                          # ProviderClient interface (compare_commits, create_pull_request, get_default_branch)
│   │   ├── github.py                        # GitHub API client
│   │   └── bitbucket.py                     # Bitbucket API client
│   │
│   ├── config/                              # Configuration
│   │   ├── __init__.py
│   │   ├── settings.py                      # Pydantic BaseSettings
│   │   ├── database.py
│   │   ├── mcp.py
│   │   ├── agents.py                        # Per-agent model configuration
│   │   ├── autodoc_config.py                # .autodoc.yaml schema
│   │   ├── prefect.py                      # Work pool, deployment prefix, concurrency limits
│   │   └── logging.yaml
│   │
│   └── shared/                              # Shared Utilities
│       ├── __init__.py
│       ├── exceptions/
│       │   ├── __init__.py
│       │   ├── base.py                     # TransientError, PermanentError, QualityError hierarchy
│       │   ├── repository.py
│       │   ├── job.py
│       │   └── agent.py
│       ├── logging/
│       │   ├── __init__.py
│       │   └── logger.py                    # JSON structured logging with correlation IDs
│       ├── telemetry/
│       │   ├── __init__.py
│       │   ├── setup.py                     # TracerProvider + LoggingInstrumentor configuration
│       │   └── metrics.py                   # aggregate_job_metrics, calculate_cost
│       ├── security/
│       │   ├── __init__.py
│       │   └── encryption.py               # Token encryption/decryption
│       └── utils/
│           ├── __init__.py
│           ├── async_utils.py
│           └── file_utils.py
│
├── deployment/
│   ├── Dockerfile                           # API service image (lightweight: FastAPI + Prefect client)
│   ├── Dockerfile.flow                      # Flow runner image (heavy: AI libs + tools + flow code)
│   ├── docker-compose.yml                   # Full stack: API + Worker + Prefect Server + PostgreSQL
│   ├── docker-compose.dev.yml               # Infrastructure only: Prefect Server + PostgreSQL
│   ├── docker-compose.test.yml
│   │
│   ├── k8s/
│   │   ├── deployment.yaml
│   │   ├── prefect-worker.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   └── secrets.yaml
│   │
│   └── scripts/
│       ├── init-db.sql                      # Creates `prefect` database for Prefect Server (mounted into PostgreSQL container)
│       ├── dev_setup.sh
│       └── run_migrations.sh
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   │
│   ├── unit/
│   │   ├── test_services/
│   │   ├── test_repositories/
│   │   ├── test_agents/
│   │   └── test_workflows/
│   │
│   ├── integration/
│   │   ├── test_api/
│   │   │   ├── test_repositories_api.py
│   │   │   ├── test_jobs_api.py
│   │   │   └── test_documents_api.py
│   │   ├── test_database/
│   │   ├── test_agents/
│   │   │   ├── test_structure_extractor.py
│   │   │   ├── test_page_generator.py
│   │   │   └── test_readme_distiller.py
│   │   └── test_workflows/
│   │       ├── test_documentation_flow.py
│   │       └── test_incremental_flow.py
│   │
│   └── fixtures/
│       ├── sample_repos/
│       └── mock_data.py
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── AGENTS.md
│   ├── WORKFLOWS.md
│   ├── MCP_INTEGRATION.md
│   ├── DATABASE.md                          # PostgreSQL + pgvector design
│   └── DEPLOYMENT.md
│
├── Makefile                                 # Developer workflow: make up, make dev-up, make worker, make api, make test
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## 7. Agent Design

### BaseAgent Interface

All agents implement a common `BaseAgent` interface to decouple workflow orchestration from the underlying LLM framework (currently Google ADK). ADK-specific types and imports never leak beyond each agent module's boundary.

```
ABSTRACT CLASS BaseAgent:
    ABSTRACT ASYNC METHOD run(input: Model) -> AgentResult[Model]

CLASS AgentResult[T]:
    output: T                           # The agent's primary output
    attempts: integer                   # Number of attempts taken
    final_score: float                  # Best evaluation score achieved
    passed_quality_gate: boolean        # Whether the quality threshold was met
    below_minimum_floor: boolean        # Whether below MINIMUM_SCORE_FLOOR
    evaluation_history: list[EvaluationResult]  # All evaluation results across attempts
    token_usage: TokenUsage             # Cumulative token usage across all attempts

CLASS TokenUsage:
    input_tokens: integer               # Total input tokens across all attempts
    output_tokens: integer              # Total output tokens across all attempts
    llm_calls: integer                  # Total LLM calls (generator + critic)
    by_role: dict                       # {"generator": {input, output}, "critic": {input, output}}
```

**Design principles:**

- **Single method** — All agents expose `async run(input) -> AgentResult[output]`, nothing else
- **Pydantic in/out** — Each agent accepts and returns Pydantic models defined in its own `schemas.py`, wrapped in `AgentResult` for telemetry
- **ADK stays inside** — ADK-specific code (tool binding, prompt injection, model configuration) stays inside the agent module. The `agent.py` file wraps ADK internals and implements `BaseAgent`
- **Generator & Critic separation** — Each generating agent composes two ADK sub-agents internally: a Generator (produces content) and a Critic (evaluates against a rubric). They can use different LLM models.
- **Swappable** — Workflow tasks depend only on `BaseAgent`, making agents swappable (ADK today, raw API calls or LangChain tomorrow)
- **Session persistence** — Each agent uses ADK's `DatabaseSessionService` backed by PostgreSQL (connection string from `DATABASE_URL`) to persist session state. This enables the Generator to see its prior output and the Critic's feedback across retry attempts via the session's conversation history.
- **Per-task construction** — Agent instances are constructed per-task within Prefect workers from environment variable configuration. Each Prefect task that needs an agent (e.g., `extract_structure`, `generate_page`, `distill_readme`) creates its agent instance internally. No shared state between tasks. FastAPI's `Depends()` is used only for service injection in API route handlers (e.g., `JobService`, `WikiService`).

### Agent Implementation Pattern: Generator & Critic Loop

Each generating agent (StructureExtractor, PageGenerator, ReadmeDistiller) implements the Generator & Critic pattern. The Generator and Critic are separate ADK `LlmAgent` instances — the Critic uses a potentially different model to avoid self-reinforcing bias.

**Feedback mechanism:** The Generator's ADK session (persisted via `DatabaseSessionService` to PostgreSQL) maintains the full conversation history. On retry, the Critic's structured feedback is appended to the session as a user message, so the Generator sees its previous output and the Critic's critique in its conversation context. This leverages ADK's native session management rather than manual prompt concatenation:

```
CLASS GeneratingAgent EXTENDS BaseAgent:
    CONSTRUCTOR(generator_model, critic_model, tools, prompt, rubric, threshold, max_attempts,
                backoff_base=2.0, criterion_floors=None, session_service: DatabaseSessionService):
        // Generator: ADK LlmAgent that produces content
        self.generator = ADK LlmAgent(
            model=generator_model,
            tools=tools,
            instruction=prompt
        )

        // Critic: Separate ADK LlmAgent that evaluates content against a rubric
        self.critic = ADK LlmAgent(
            model=critic_model,
            instruction=CRITIC_SYSTEM_PROMPT,
            output_schema=EvaluationResult
        )

        self.rubric = rubric             // Weighted criteria as structured prompt
        self.threshold = threshold
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.criterion_floors = criterion_floors  // Optional per-criterion minimum scores, e.g., {"accuracy": 5.0}
        self.session_service = session_service  // DatabaseSessionService(db_url=DATABASE_URL)

    ASYNC METHOD run(input) -> AgentResult:
        best_result = NONE
        best_score = -1.0
        evaluation_history = []

        // Create a persistent session for this generation run
        session = AWAIT self.session_service.create_session(
            app_name="autodoc", user_id=input.job_id
        )

        FOR attempt IN 1..max_attempts:
            // Generate output — session carries prior attempts + Critic feedback
            IF attempt == 1:
                message = format_initial_prompt(input)
            ELSE:
                message = format_retry_prompt(eval.feedback)

            // ADK Runner executes Generator with session context
            runner = Runner(agent=self.generator, session_service=self.session_service)
            result = AWAIT runner.run(session_id=session.id, message=message)

            // Critic evaluates against weighted rubric (separate LLM call, separate session)
            TRY:
                eval = AWAIT self.critic.run(CriticInput(
                    content=result,
                    rubric=self.rubric,
                    source_context=input.source_context  // Source files for accuracy verification
                ))
            CATCH CriticFailure:
                // If Critic call fails (rate limit, timeout, malformed output),
                // treat this attempt as auto-passed with a warning.
                // This prevents Critic failures from blocking the entire generation pipeline.
                LOG.warning("Critic call failed, auto-passing attempt {attempt}")
                eval = EvaluationResult(score=self.threshold, passed=TRUE, feedback="Critic unavailable — auto-passed", criteria_scores={})
            evaluation_history.APPEND(eval)

            IF eval.score > best_score:
                best_result = result
                best_score = eval.score
                best_eval = eval

            IF eval.passed:
                RETURN AgentResult(
                    output=result,
                    attempts=attempt,
                    final_score=eval.score,
                    passed_quality_gate=TRUE,
                    below_minimum_floor=FALSE,
                    evaluation_history=evaluation_history
                )

            // Exponential backoff before next attempt
            IF attempt < max_attempts:
                AWAIT sleep(self.backoff_base * (2 ** (attempt - 1)))

        // Check minimum quality floor and per-criterion floors
        below_floor = best_score < MINIMUM_SCORE_FLOOR
        IF NOT below_floor AND self.criterion_floors:
            // Check per-criterion minimum scores (e.g., accuracy >= 5.0)
            FOR criterion, floor IN self.criterion_floors:
                IF best_eval.criteria_scores[criterion] < floor:
                    below_floor = TRUE
                    BREAK

        RETURN AgentResult(
            output=best_result,
            attempts=max_attempts,
            final_score=best_score,
            passed_quality_gate=FALSE,
            below_minimum_floor=below_floor,
            evaluation_history=evaluation_history
        )
```

### Critic Rubric Format

The Critic sub-agent receives a structured rubric as part of its input. Each criterion is a prompt fragment with a weight, question, and scoring guidance. The `criteria/` directory in each agent module contains these rubric definitions:

```
CriticInput:
    content: any                        # The Generator's output to evaluate
    rubric: list[RubricCriterion]       # Weighted evaluation criteria
    source_context: optional list[SourceFile]  # Source files for accuracy verification (Critic can check code references)

SourceFile:
    path: string                        # Relative file path
    content: string                     # File content (or relevant excerpt)

RubricCriterion:
    name: string                        # e.g., "coverage", "accuracy"
    weight: float                       # e.g., 0.4 (must sum to 1.0)
    question: string                    # What the Critic should assess
    scoring_guidance: string            # How to score 1-10 for this criterion

EvaluationResult:
    score: float                        # Weighted average, 1-10
    passed: boolean                     # score >= threshold
    feedback: string                    # Specific improvement suggestions
    criteria_scores: dict               # {"coverage": 8.5, "hierarchy": 7.0, ...}
    criteria_weights: dict              # {"coverage": 0.4, "hierarchy": 0.3, ...}
```

### Token & Quality Metrics Aggregation

Token usage and quality metrics are carried by each `AgentResult` via the `token_usage` field. No separate telemetry service or in-process span storage is needed. The flow aggregates metrics from all `AgentResult` instances at the end of the job:

```
FUNCTION aggregate_job_metrics(
    structure_results: list[AgentResult],
    page_results: list[AgentResult],
    readme_results: list[AgentResult]
) -> JobMetrics:
    all_results = structure_results + page_results + readme_results

    RETURN JobMetrics(
        total_input_tokens=SUM(r.token_usage.input_tokens FOR r IN all_results),
        total_output_tokens=SUM(r.token_usage.output_tokens FOR r IN all_results),
        by_agent={
            "structure_extractor": aggregate_tokens(structure_results),
            "page_generator": aggregate_tokens(page_results),
            "readme_distiller": aggregate_tokens(readme_results),
        },
        estimated_cost_usd=calculate_cost(all_results),
        total_llm_calls=SUM(r.token_usage.llm_calls FOR r IN all_results),
        evaluation_summary={
            per_page_scores: {r.output.page_key: r.final_score FOR r IN page_results},
            avg_score: AVG(r.final_score FOR r IN page_results),
            pages_below_floor: [r.output.page_key FOR r IN page_results WHERE r.below_minimum_floor],
            regeneration_rate: COUNT(r FOR r IN page_results WHERE r.attempts > 1) / COUNT(page_results)
        }
    )

JobMetrics:
    total_input_tokens: integer
    total_output_tokens: integer
    by_agent: dict                      # {agent_name: {input_tokens, output_tokens}}
    estimated_cost_usd: float
    total_llm_calls: integer
    evaluation_summary: dict            # Per-page scores, avg, floor violations
```

OpenTelemetry's `LoggingInstrumentor` automatically injects `trace_id` and `span_id` into all structured log entries, enabling end-to-end correlation in log aggregation systems (ELK, Loki, CloudWatch) without storing spans in-process.

### StructureExtractor

**Entry point agent** — analyzes repository and extracts documentation structure:
- Receives a pre-computed `FileTree` (produced by the `scan_file_tree` task) containing only non-excluded files, with a human-readable directory tree and language statistics
- Uses the file tree to understand repository layout, detect languages, frameworks, and patterns without scanning the filesystem itself
- Determines which code areas need documentation pages and how to organize them
- Evaluated via Generator + Critic loop against structure criteria
- Outputs `PageStructure` with list of pages to generate

**Output schema:**

```
PageSpec:
    id: string
    title: string
    description: string
    type: string                    # "api", "module", "class", "overview"
    importance: string              # "high", "medium", "low"
    source_files: list[string]      # Relative file paths
    related_pages: list[string]     # page_key references
    parent_id: optional string

PageStructure:
    title: string
    description: string
    pages: list[PageSpec]
    sections: dict                  # Navigation hierarchy (JSONB)
```

**Evaluation criteria (embedded):**

| Criterion | Weight | Question |
|-----------|--------|----------|
| Coverage | 40% | Does the structure cover all significant code areas? |
| Hierarchy | 30% | Is the organization logical and navigable? |
| Granularity | 20% | Right level of detail (not too broad, not too fine)? |
| Completeness | 10% | Are all mandatory sections present? |

**Evaluation result schema:**

```
StructureEvaluationResult:
    score: float                    # Weighted average, 1-10
    passed: boolean                 # score >= threshold
    feedback: string                # Improvement suggestions
    criteria_scores: dict           # {"coverage": 8.5, "hierarchy": 7.0, ...}
    criteria_weights: dict          # {"coverage": 0.4, "hierarchy": 0.3, ...}
```

### PageGenerator

Generates a single documentation page with embedded quality evaluation:
- Receives `PageSpec` from StructureExtractor
- Reads relevant source files
- Uses `style` settings from `.autodoc.yaml` to adjust prompt parameters (audience, tone, detail level)
- Injects `custom_instructions` from `.autodoc.yaml` into prompts
- Generates documentation content
- Evaluated via Generator + Critic loop against page criteria
- Returns the best evaluated result

**Evaluation criteria (embedded):**

| Criterion | Weight | Question |
|-----------|--------|----------|
| Accuracy | 35% | Are code references and claims correct? |
| Completeness | 25% | Does it cover all relevant code elements? |
| Readability | 20% | Is it clear, well-structured, junior-dev friendly? |
| Citations | 10% | Are claims backed by file references? |
| Structure | 10% | Is internal page organization sensible? |

**Evaluation result schema:**

```
PageEvaluationResult:
    page_id: string
    score: float                    # Weighted average, 1-10
    passed: boolean                 # score >= threshold
    feedback: string                # Improvement suggestions
    criteria_scores: dict           # {"accuracy": 9.0, "completeness": 7.5, ...}
    criteria_weights: dict          # {"accuracy": 0.35, "completeness": 0.25, ...}
```

**Output schema:**

```
GeneratedPage:
    page_key: string                # URL-friendly identifier (from PageSpec.id)
    title: string
    content: string                 # Full markdown content
    source_files_read: list[string] # Which files were actually read (may differ from PageSpec)
    code_references: list[CodeRef]  # Extracted code references for citation validation
    word_count: integer

CodeRef:
    file_path: string
    line_range: optional string     # e.g., "42-67"
    symbol: optional string         # e.g., "class UserService"
```

This enables the Critic to validate code references programmatically against `source_context`.

### ReadmeDistiller

Distills all generated wiki pages into a single cohesive README.md. Like StructureExtractor and PageGenerator, uses the Generator & Critic loop pattern:
- Receives ALL generated wiki pages (updated + unchanged in incremental mode)
- Eliminates duplicate information appearing across multiple wiki pages
- Maintains a logical flow: Overview → Quickstart → Architecture → Core Modules → Configuration → API/Interfaces → Testing → Deployment → Contributing
- Is self-contained and readable without the structured wiki
- Respects `.autodoc.yaml` preferences for `readme.max_length`, `readme.include_toc`, `readme.include_badges`
- Internally evaluated and retried against README-specific criteria via the Critic sub-agent

**Evaluation criteria (embedded):**

| Criterion | Weight | Question |
|-----------|--------|----------|
| Coherence | 30% | Does the README read as a single cohesive document (not a concatenation of wiki pages)? |
| Completeness | 25% | Does it cover all significant aspects of the codebase? |
| Deduplication | 20% | Is redundant information across wiki pages properly merged? |
| Readability | 15% | Is it clear, well-structured, and appropriate for the target audience? |
| Formatting | 10% | Is markdown well-formed, TOC correct, sections logically ordered? |

**Evaluation result schema:**

```
ReadmeEvaluationResult:
    score: float                     # Weighted average, 1-10
    passed: boolean                  # score >= threshold
    feedback: string                 # Improvement suggestions
    criteria_scores: dict            # {"coherence": 8.0, "completeness": 7.5, ...}
    criteria_weights: dict           # {"coherence": 0.3, "completeness": 0.25, ...}
```

**Schemas:**

```
ReadmeInput:
    pages: list[GeneratedPage]       # All wiki pages (updated + unchanged)
    repo_name: string
    repo_description: string
    autodoc_config: optional dict    # From .autodoc.yaml if present

ReadmeOutput:
    content: string                  # Full markdown content of the README
    sections_covered: list[string]   # Which wiki sections were distilled
    deduplication_notes: string      # What was merged/removed to avoid redundancy
    word_count: integer
```

### Error Hierarchy

All exceptions follow a structured three-tier hierarchy defined in `shared/exceptions/base.py`:

```
CLASS AutodocError(Exception):
    // Base for all application errors

CLASS TransientError(AutodocError):
    // Retryable errors — Prefect task retry logic keys off this type
    // Examples: LLM rate limit, network timeout, provider API 5xx, S3 upload failure

CLASS PermanentError(AutodocError):
    // Non-retryable errors — fail immediately, no retry
    // Examples: invalid .autodoc.yaml config, repository not found, invalid access token,
    //           MAX_REPO_SIZE exceeded, unsupported provider

CLASS QualityError(AutodocError):
    // Agent quality gate failure — handled by the Generator & Critic loop
    // Carries evaluation details (score, feedback, criteria_scores)
    // Not retried at Prefect task level — the agent loop handles retry with feedback
```

This enables Prefect's retry decorator to distinguish between errors that should trigger a task retry (transient) and errors that should fail the task immediately (permanent). The agent's internal Generator & Critic loop handles quality failures independently.

### Quality Gate Behavior

All three generating agents (StructureExtractor, PageGenerator, ReadmeDistiller) track the **best attempt** (highest score), not the last attempt. The `MINIMUM_SCORE_FLOOR` (default: 4.0) prevents shipping garbage. In addition to the overall floor, configurable **per-criterion minimum scores** (e.g., accuracy must be >= 5.0) prevent masking critical failures where one criterion scores very low but the weighted average still passes. If any agent's best attempt after all retries is still below the floor or violates a per-criterion minimum, the entire job is marked as `FAILED`. Jobs are `COMPLETED` (all agents passed), `FAILED`, or `CANCELLED` (user-initiated cancellation).

**Partial failure handling:** Since each Prefect task commits atomically (transaction scope = task), pages that pass quality gates are persisted even if a subsequent page fails. When a page failure causes the job to be marked `FAILED`, all already-committed pages remain in the database as partial results. The job's `quality_report` includes a detailed breakdown of which pages passed, which failed, and their scores. This allows users to inspect partial documentation via the API and re-trigger the job to regenerate only the failed pages (on retry, the flow resumes from the last successful task).

The `AgentResult` wrapper returned by each agent carries the full evaluation history and token usage, enabling the flow's `aggregate_job_metrics()` to compile the Job's `quality_report` JSONB field:
- Per-page scores and evaluation history
- Overall average score
- Which pages required regeneration (attempts > 1)
- Which pages fell below the floor
- README quality score

### Prefect Workflow Orchestration

#### Why Prefect?

| Requirement | Prefect Feature |
|-------------|-----------------|
| API-triggered jobs | Deployments with API/webhook triggers |
| Clone repository | Task with retry logic, timeout handling |
| Track job status | Built-in state management (Pending, Running, Completed, Failed) |
| Parallel page generation | Native async support, Prefect futures for fan-out |
| Observability | Prefect UI for monitoring flows and tasks |
| Resumability | Resume failed flows from last successful task |
| Concurrency control | Limit parallel agents to avoid rate limits |

#### Main Documentation Flow

```python
@task(retries=3, retry_delay_seconds=10, timeout_seconds=300)
async def clone_repository(repo_url, branch, job_id, access_token=None) -> tuple[str, str]: ...

@task
async def discover_autodoc_configs(repo_path: str) -> list[tuple[str, AutodocConfig]]: ...

@task
async def scan_file_tree(scope_root: str, config: AutodocConfig) -> FileTree: ...

@task(retries=2, retry_delay_seconds=30, timeout_seconds=600)
async def extract_structure(scope_root, file_tree, config) -> AgentResult[PageStructure]: ...

@task(timeout_seconds=300, tags=["page-generation"])
async def generate_page(page_spec, scope_root, config) -> AgentResult[GeneratedPage]: ...

@task
async def distill_readme(pages, repo_name, description, config) -> AgentResult[ReadmeOutput]: ...

@task
async def generate_embeddings(job_id, pages) -> None: ...

@task
async def store_wiki(job_id, repo_id, structure, pages, sha, branch, scope) -> None: ...


@flow(name="documentation-flow")
async def documentation_flow(job_id: str, repository_id: str, branch: str = "main", dry_run: bool = False):
    try:
        repo = await get_repository(repository_id)
        repo_path, commit_sha = await clone_repository(repo.url, branch, job_id, repo.access_token)
        scopes = await discover_autodoc_configs(repo_path)

        # Fan-out: process all scopes in parallel (independent sub-flows)
        scope_futures = [
            process_scope.submit(
                job_id, repository_id, repo, Path(repo_path) / scope_path, scope_path,
                config, commit_sha, branch, dry_run
            )
            for scope_path, config in scopes
        ]
        all_scope_results = [f.result() for f in scope_futures]

        if dry_run:
            return {"scopes": all_scope_results, "dry_run": True}

        # Aggregate token_usage + quality metrics from all AgentResults
        job_metrics = aggregate_job_metrics(all_scope_results)

        readme_files = [
            {"path": str(Path(r["scope_path"]) / r["config"].readme.output_path),
             "content": r["readme"].content}
            for r in all_scope_results
        ]

        # Close any existing autodoc PRs for this branch before creating a new one
        await close_stale_autodoc_prs(repo, branch)
        pr_url = await create_pull_request(repo_path, repo, readme_files)
        await update_job(job_id, COMPLETED, pr_url, job_metrics)
        await fire_webhook(job_id)

        return {"scopes": all_scope_results, "pr_url": pr_url, "metrics": job_metrics}
    finally:
        await archive_adk_sessions(job_id)
        await cleanup_repository(repo_path)


@flow(name="process-scope")
async def process_scope(job_id, repo_id, repo, scope_root, scope_path, config, sha, branch, dry_run):
    """Sub-flow: processes a single documentation scope."""
    file_tree = await scan_file_tree(scope_root, config)
    structure_result = await extract_structure(scope_root, file_tree, config)
    structure = structure_result.output

    if dry_run:
        return {"scope_path": scope_path, "structure": structure, "file_tree": file_tree,
                "dry_run": True, "estimated_pages": len(structure.pages)}

    # Fan-out: generate pages in parallel (respects page-generation concurrency limit)
    page_futures = [generate_page.submit(ps, scope_root, config) for ps in structure.pages]
    page_results = [f.result() for f in page_futures]
    pages = [r.output for r in page_results]

    await store_wiki(job_id, repo_id, structure, pages, sha, branch, scope_path)

    # Parallel: embeddings + README distillation
    embed_future = generate_embeddings.submit(job_id, pages)
    readme_result = await distill_readme(pages, repo.name, repo.description, config)
    embed_future.result()  # wait for embeddings

    return {"scope_path": scope_path, "config": config, "pages": pages, "readme": readme_result.output}
```

#### Incremental Update Flow

When a repository already has documentation (one or more `WikiStructure` records exist with a `commit_sha` for the given branch), an incremental update uses the provider's compare API to identify changed files without cloning. The baseline SHA is `min(commit_sha)` across all scopes — this is a safe choice after partial failures where different scopes may be at different commits. If changes are detected, the repository is cloned (depth=1), scopes are re-discovered, and each scope's file tree is scanned and pruned. Only affected pages within affected scopes are regenerated. If structural changes are detected within a scope (new modules, deleted directories), that scope's structure is re-extracted. New scopes (new `.autodoc.yaml` files) trigger full generation for that scope only:

```python
@flow(name="incremental-update-flow")
async def incremental_update_flow(job_id: str, repository_id: str, branch: str = "main", dry_run: bool = False):
    try:
        repo = await get_repository(repository_id)
        previous_scopes = await get_previous_documentation(repository_id, branch)

        if not previous_scopes:
            # No previous docs — fall back to full generation
            return await documentation_flow(job_id, repository_id, branch, dry_run)

        # Diff via provider API (no clone yet)
        # Use min(commit_sha) across all scopes — safe baseline after partial failures
        baseline_sha = min(s.commit_sha for s in previous_scopes)
        changed_files = await diff_changed_files_via_provider(repo.url, baseline_sha, branch)

        if not changed_files:
            await update_job(job_id, COMPLETED, quality_report=None, token_usage=None)
            return {"status": "no_changes", "pages_updated": 0}

        if dry_run:
            return {"status": "dry_run", "changed_files": len(changed_files),
                    "baseline_sha": baseline_sha, "files": changed_files}

        # Clone only after confirming changes exist
        repo_path, commit_sha = await clone_repository(repo.url, branch, job_id, repo.access_token)
        scopes = await discover_autodoc_configs(repo_path)

        # Fan-out: process all scopes in parallel
        scope_futures = [
            process_incremental_scope.submit(
                job_id, repository_id, repo, repo_path, scope_path,
                config, previous_scopes, changed_files, commit_sha, branch
            )
            for scope_path, config in scopes
        ]
        all_scope_results = [f.result() for f in scope_futures]

        # Aggregate token_usage + quality metrics from all AgentResults
        job_metrics = aggregate_job_metrics(all_scope_results)

        readme_files = [
            {"path": str(Path(r["scope_path"]) / r["config"].readme.output_path),
             "content": r["readme"].content}
            for r in all_scope_results if r.get("readme")
        ]

        # Close any existing autodoc PRs for this branch before creating a new one
        await close_stale_autodoc_prs(repo, branch)
        pr_url = await create_pull_request(repo_path, repo, readme_files)
        await update_job(job_id, COMPLETED, pr_url, job_metrics)
        await fire_webhook(job_id)

    finally:
        await archive_adk_sessions(job_id)
        await cleanup_repository(repo_path)


@flow(name="process-incremental-scope")
async def process_incremental_scope(
    job_id, repo_id, repo, repo_path, scope_path, config,
    previous_scopes, changed_files, commit_sha, branch
):
    """Sub-flow: incrementally processes a single documentation scope."""
    scope_root = Path(repo_path) / scope_path
    previous = find_previous_scope(previous_scopes, scope_path)

    # Filter changes to this scope
    scope_changed = [f for f in changed_files if f.startswith(scope_path)]

    if not scope_changed and previous:
        return {"scope_path": scope_path, "pages_updated": 0, "status": "unchanged"}

    file_tree = await scan_file_tree(scope_root, config)

    if not previous:
        # New scope — full generation
        structure = (await extract_structure(scope_root, file_tree, config)).output
        affected_pages = structure.pages
    else:
        # Detect structural changes within scope
        structural_change = await detect_structural_changes(scope_changed, previous.structure)
        if structural_change.detected:
            structure = (await extract_structure(scope_root, file_tree, config)).output
            affected_pages = derive_affected_pages(structure, previous, scope_changed)
        else:
            structure = previous.structure
            affected_pages = await map_files_to_pages(scope_changed, previous.pages)

    if not affected_pages and previous:
        return {"scope_path": scope_path, "pages_updated": 0, "status": "no_affected_pages"}

    # Fan-out: regenerate affected pages
    page_futures = [generate_page.submit(ps, scope_root, config) for ps in affected_pages]
    updated_pages = [f.result().output for f in page_futures]

    # Merge with unchanged pages (handles page deletion for removed source files)
    if previous:
        all_pages = await merge_pages(
            updated_pages, previous.pages,
            affected_ids=[p.id for p in affected_pages],
            deleted_files=scope_changed
        )
    else:
        all_pages = updated_pages

    await store_wiki(job_id, repo_id, structure, all_pages, commit_sha, branch, scope_path)

    # Parallel: embeddings + README
    embed_future = generate_embeddings.submit(job_id, updated_pages)
    readme_result = await distill_readme(all_pages, repo.name, repo.description, config)
    embed_future.result()

    return {
        "scope_path": scope_path, "config": config,
        "pages_updated": len(updated_pages), "readme": readme_result.output
    }
```

#### Prefect Tasks

**clone_repository** — Clone a git repository to a temp directory. Returns `(repo_path, commit_sha)` — runs `git rev-parse HEAD` after cloning to obtain the commit SHA. Retries 3 times, 10s delay, 5min timeout. Injects access token into URL if provided. Uses shallow clone (depth=1) for speed. Checks total repo size against `MAX_REPO_SIZE` limit.

**cleanup_repository** — Remove cloned repository temp directory.

**discover_autodoc_configs** — Scan the cloned repository for all `.autodoc.yaml` files. Returns a list of `(scope_path, AutodocConfig)` pairs where `scope_path` is the directory containing the config file (relative to repo root, e.g., `"."`, `"packages/auth"`). If no `.autodoc.yaml` is found anywhere, returns `[(".", default_config)]`. Each config is validated independently. **Scope overlap auto-exclusion**: when multiple scopes exist, parent scopes automatically exclude subdirectories that have their own `.autodoc.yaml`. For example, if both `"."` and `"packages/auth"` have configs, the root scope's config is augmented with an implicit `exclude: ["packages/auth/"]` to prevent duplicate coverage.

**load_autodoc_config** — Read and parse a single `.autodoc.yaml` from a given path. Performs strict validation: returns defaults if absent, returns warnings for unknown keys, fails on invalid values. Validation results are stored in the job record.

**scan_file_tree** — Walk the cloned repository directory tree, apply `include`/`exclude` patterns from the autodoc config (or defaults if no `.autodoc.yaml`), physically remove excluded files and directories from the clone, and return a `FileTree`. This ensures all downstream agents only see relevant files and receive a pre-computed overview of the repository layout. The physical removal means agents cannot accidentally read or reference excluded content. Enforces configurable limits: `MAX_TOTAL_FILES` (fail if exceeded after pruning), `MAX_FILE_SIZE` (skip files larger than threshold). Emits a warning (but proceeds) if pruning removes >90% of files. Logs pruning summary (files removed, files remaining, patterns applied). Note: since `git clone` only includes tracked files, `.gitignore`-excluded untracked files are never present in the clone; the default exclude patterns cover common tracked-but-ignorable directories.

```
FileTree:
    tree_text: string               # Human-readable directory tree (like `tree` command output)
    file_paths: list[string]        # All remaining file paths (relative to repo root)
    total_files: integer
    total_directories: integer
    language_stats: dict            # Extension → file count mapping (e.g., {".py": 45, ".js": 12})
```

**extract_structure** — Run StructureExtractor agent with the pre-computed `FileTree` as context (Generator + Critic loop internally). The file tree gives the agent a complete picture of the repository's layout, languages, and file distribution without needing to scan the filesystem. Returns `AgentResult[PageStructure]`. Retries 2 times at task level, 30s delay.

**generate_page** — Run PageGenerator agent for a single page (Generator + Critic loop internally). Returns `AgentResult[GeneratedPage]`. Respects concurrency limit (`page-generation` slot).

**distill_readme** — Run ReadmeDistiller agent on all pages (Generator + Critic loop internally). Returns `AgentResult[ReadmeOutput]`.

**generate_embeddings** — Generate vector embeddings for all wiki pages using `EmbeddingService`. Updates `wiki_pages.content_embedding` column in the database. Runs in parallel with `distill_readme`.

**get_previous_documentation** — Retrieve the most recent wiki structures, pages, and commit SHA for all scopes of a given `(repository_id, branch)` from the database. Returns a list of `{scope_path, structure, pages, commit_sha}` entries. Used by the incremental flow to determine the baseline for change detection across all scopes.

**detect_structural_changes** — Compare changed files against existing page structure. Checks for: new top-level directories not covered by existing pages, deleted modules whose pages should be removed, new file types suggesting new documentation sections. Returns `structural_change_detected` boolean and `new_file_groups`.

**close_stale_autodoc_prs** — Before creating a new PR, search for open PRs with the `autodoc/` branch prefix targeting the same base branch via the provider API. Close each with a comment ("Superseded by documentation job {job_id}") and delete the stale branch. Logs the number of PRs closed. Non-fatal — if cleanup fails, the new PR is still created.

**create_pull_request** — Create branch `autodoc/{repo_name}-{branch}-{job_id_short}-{YYYY-MM-DD}`, commit all scope README files (each at its `scope_path/output_path`), open PR from that branch back to the repository's default branch via provider API. PR body includes: number of scopes processed, number of pages updated, overall quality score, and a link to `GET /jobs/{id}` for detailed per-page breakdown. Uses the `ProviderClient` abstraction for GitHub/GitLab/Bitbucket.

**diff_changed_files_via_provider** — Call the provider's compare API (GitHub: `GET /repos/{owner}/{repo}/compare/{base}...{head}`, GitLab: `GET /projects/{id}/repository/compare`, Bitbucket: `GET /2.0/repositories/{workspace}/{repo}/diff/{spec}`) to get the list of changed file paths without cloning the repository. This avoids cloning for no-change incremental runs.

**derive_affected_pages** — After a structural re-extraction, compare the new structure against the previous structure and changed files. Marks new pages (not in previous structure) and pages whose `source_files` overlap with `changed_files` as affected. Returns the list of affected `PageSpec` entries.

**map_files_to_pages** — Cross-reference changed files against each page's `source_files` to identify affected pages.

**merge_pages** — Combine updated pages with unchanged pages from previous documentation. Also handles page deletion: pages whose **all** `source_files` are in the `deleted_files` list are removed from the merged result. Pages with some remaining source files are included (they will have been flagged for regeneration by `map_files_to_pages`). Receives `deleted_files` from the diff result.

**store_wiki** — Persist wiki structure and pages to PostgreSQL within a single transaction (one Prefect task = one transaction scope). Creates a new version for the given `(repository_id, branch, scope_path)`. Enforces the 3-version retention policy per scope — when a 4th version is created, the oldest is deleted along with all its pages and embeddings via FK cascade.


**update_job** — Update job record with final status, quality report, token usage, and PR URL. Called at the end of both flows.

**fire_webhook** — POST job completion/failure notification to the callback URL if configured on the job. Retries up to 3 times with exponential backoff (2s, 4s, 8s) on transient failures (HTTP 5xx, connection errors). Logs a warning on final failure but does not block job completion. Delivery is best-effort.

**reconcile_stale_jobs** — Startup routine that scans the `jobs` table for records stuck in `RUNNING` status. For each, queries the corresponding Prefect flow run state. If the flow is no longer active (completed, failed, cancelled, or missing), updates the job status accordingly. Handles crash recovery and worker restarts.

**cleanup_orphaned_repos** — Scan temp directory for `autodoc_*` dirs older than 1 hour and remove them.

**archive_adk_sessions** — Archive ADK sessions to S3 after each flow run for future analysis and agent improvement. Lists all sessions for the job via `session_service.list_sessions()`, reads full session data, serializes to JSON and uploads to S3 (`s3://autodoc-sessions/{job_id}/`), then deletes from PostgreSQL via `session_service.delete_session()`. Runs in the flow's `FINALLY` block.

**get_repository** — Resolve `repository_id` to full repository details (URL, name, description, access token, default branch). Called at the start of each flow to provide all downstream tasks with repository metadata.

#### Prefect Configuration

```
WORKFLOW_CONFIG:
    max_concurrent_page_generations: 5
    default_retries: 3
    default_retry_delay_seconds: 30
    backoff_base_seconds: 2.0           # Base for exponential backoff in agent retry loops
    clone_timeout_seconds: 300
    extraction_timeout_seconds: 600
    generation_timeout_seconds: 300
```

Concurrency limits are created on startup using Prefect's concurrency API with the tag `page-generation`. Page generation concurrency is the single knob governing parallelism — LLM call concurrency is an emergent property of how many pages are being generated simultaneously.

#### Work Pool Strategy

Environment-specific work pools decouple flow code from infrastructure:

| Environment | Work Pool | Type | Behavior |
|-------------|-----------|------|----------|
| Local dev | `local-dev` | `process` | Flows run as subprocesses on the developer's machine |
| Production | `k8s-pool` | `kubernetes` | Each flow run gets its own Kubernetes pod |

The `PREFECT_WORK_POOL` environment variable selects the active pool. No code changes between environments — only the work pool configuration differs.

#### API Deployment & Environment Switching

Two Prefect deployments are created per environment, selected via the `AUTODOC_FLOW_DEPLOYMENT_PREFIX` env var:

| Deployment Name | Flow | Tags |
|-----------------|------|------|
| `{prefix}/documentation` | `documentation_flow` | `[api, documentation]` |
| `{prefix}/incremental` | `incremental_update_flow` | `[api, documentation, incremental]` |

- **Local**: `AUTODOC_FLOW_DEPLOYMENT_PREFIX=dev` → deployments target `local-dev` process pool
- **Production**: `AUTODOC_FLOW_DEPLOYMENT_PREFIX=prod` → deployments target `k8s-pool` Kubernetes pool

The `JobService` reads the prefix from configuration and constructs the full deployment name at runtime.

#### Job Service Integration

```
CLASS JobService:
    CONSTRUCTOR(job_repo):
        self.job_repo = job_repo

    ASYNC METHOD create_job(repo_id, branch="main", mode="full", callback_url=None, dry_run=FALSE) -> Job:
        // Idempotency: check for existing PENDING/RUNNING job for same (repo_id, branch, mode, dry_run)
        existing = AWAIT self.job_repo.find_active(repo_id, branch, mode, dry_run)
        IF existing:
            RETURN existing  // Return existing job instead of creating duplicate

        // Create job record with PENDING status
        job = Job(repo_id, branch, status=PENDING, mode=mode,
                  callback_url=callback_url, dry_run=dry_run)
        job = AWAIT self.job_repo.create(job)

        // Select deployment based on mode (prefix from AUTODOC_FLOW_DEPLOYMENT_PREFIX env var)
        prefix = config.deployment_prefix  // e.g., "dev" or "prod"
        deployment = f"{prefix}/incremental" IF mode == "incremental"
                     ELSE f"{prefix}/documentation"

        // Trigger Prefect flow (non-blocking)
        flow_run = AWAIT run_deployment(deployment,
            {job_id, repository_id: repo_id, branch, dry_run}, timeout=0)

        // Update job with flow run ID
        job.prefect_flow_run_id = flow_run.id
        job.status = RUNNING
        AWAIT self.job_repo.update(job)

        RETURN job

    ASYNC METHOD list_jobs(repo_id=None, status=None, cursor=None, limit=20) -> PaginatedResult[Job]:
        // Lightweight proxy over Prefect's flow run API + local job records
        // Filters by repository_id, status, with cursor-based pagination
        jobs = AWAIT self.job_repo.list(repo_id, status, cursor, limit)

        // Sync status from Prefect for any RUNNING jobs in the result set
        FOR job IN jobs WHERE job.status == RUNNING:
            AWAIT self._sync_job_status(job)

        RETURN PaginatedResult(items=jobs, next_cursor=compute_cursor(jobs))

    ASYNC METHOD get_job_status(job_id) -> Job:
        job = AWAIT self.job_repo.get_by_id(job_id)

        IF job.prefect_flow_run_id AND job.status == RUNNING:
            AWAIT self._sync_job_status(job)

        RETURN job

    ASYNC METHOD cancel_job(job_id) -> Job:
        job = AWAIT self.job_repo.get_by_id(job_id)

        IF job.status NOT IN (PENDING, RUNNING):
            RAISE InvalidStateError("Can only cancel PENDING or RUNNING jobs")

        IF job.prefect_flow_run_id:
            // Use Prefect's native cancellation
            AWAIT prefect_client.set_flow_run_state(
                job.prefect_flow_run_id, state=Cancelled()
            )

        job.status = CANCELLED
        AWAIT self.job_repo.update(job)
        RETURN job

    ASYNC METHOD retry_job(job_id) -> Job:
        job = AWAIT self.job_repo.get_by_id(job_id)

        IF job.status != FAILED:
            RAISE InvalidStateError("Can only retry FAILED jobs")

        // Use Prefect's native flow resume — restarts from last successful task
        flow_run = AWAIT prefect_client.retry_flow_run(job.prefect_flow_run_id)

        job.status = RUNNING
        job.error_message = NONE
        AWAIT self.job_repo.update(job)
        RETURN job

    ASYNC METHOD _sync_job_status(job) -> VOID:
        // Sync status from Prefect
        flow_run = AWAIT prefect_client.read_flow_run(job.prefect_flow_run_id)

        IF flow_run.state.is_completed():
            job.status = COMPLETED
        ELSE IF flow_run.state.is_failed():
            job.status = FAILED
            job.error_message = flow_run.state.message
        ELSE IF flow_run.state.is_cancelled():
            job.status = CANCELLED

        AWAIT self.job_repo.update(job)
```

---

## 8. Repository Configuration

Different projects need different documentation styles. A `.autodoc.yaml` configuration file defines a **documentation scope** — the directory it resides in becomes the root of that scope. A single `.autodoc.yaml` at the repository root covers the entire repo. For monorepos, multiple `.autodoc.yaml` files can exist in different directories, each defining an independent documentation scope with its own wiki structure, pages, and README.

### Monorepo Discovery

After cloning, the flow scans the repository for all `.autodoc.yaml` files. Each discovered file defines a scope:

- **Scope path**: The directory containing the `.autodoc.yaml` (e.g., `.` for root, `packages/auth`, `services/billing`)
- **Scope isolation**: Each scope gets its own StructureExtractor, PageGenerators, and ReadmeDistiller run
- **Scope overlap auto-exclusion**: When multiple scopes exist, parent scopes automatically exclude subdirectories that have their own `.autodoc.yaml`. For example, if both `.` and `packages/auth` have configs, the root scope implicitly excludes `packages/auth/` from its file tree to prevent duplicate coverage
- **Include/exclude paths**: Relative to the scope root (the `.autodoc.yaml` directory), not the repo root
- **README output**: `readme.output_path` is relative to the scope root
- **Database keys**: `wiki_structures` are keyed on `(repository_id, branch, scope_path)`
- **Parallel processing**: All discovered scopes are processed in parallel as independent sub-flows

If no `.autodoc.yaml` is found anywhere in the repository, sensible defaults are applied with `scope_path='.'` (the entire repo is one scope).

### Specification

```yaml
# .autodoc.yaml — placed in any directory to define a documentation scope
version: 1

# What to document (glob patterns)
include:
  - src/
  - lib/
  - app/

# What to exclude (glob patterns)
exclude:
  - node_modules/
  - dist/
  - build/
  - "*.test.*"
  - "*.spec.*"
  - __pycache__/
  - .venv/
  - vendor/
  - coverage/

# Documentation style
style:
  audience: "junior-developer"    # junior-developer | senior-developer | mixed
  tone: "tutorial"                # tutorial | reference | explanation
  detail_level: "comprehensive"   # concise | standard | comprehensive

# Custom instructions for documentation generation (injected into agent prompts as-is)
custom_instructions: |
  DPU stands for "Data Processing Unit".
  "Saga" refers to a distributed transaction pattern used in our order service.
  Always document error handling patterns in detail.
  Use British English spelling.

# README preferences
readme:
  output_path: "README.md"        # Path for generated README, relative to this .autodoc.yaml's directory (default: "README.md")
  max_length: null                # null = unlimited, or integer word count (e.g., 5000)
  include_toc: true
  include_badges: true

# Pull request preferences
pull_request:
  auto_merge: false
  reviewers: ["@team-leads"]
  # Note: PRs always target the repository's default branch (configured at registration)
```

### Include/Exclude Semantics

- `include: []` (empty or omitted) — all files in the repository are included (minus excludes)
- `include: ["src/", "lib/"]` (non-empty) — ONLY files under these paths are included (minus excludes)
- `exclude` patterns are always applied on top of the include set
- Since `git clone` only includes tracked files, untracked files covered by `.gitignore` are never present in the clone. The default exclude patterns handle common tracked-but-ignorable directories (`node_modules/`, `dist/`, `build/`, etc.)

### How Agents Use This Config

- A Prefect task `discover_autodoc_configs(repo_path)` scans the cloned repository for all `.autodoc.yaml` files, returning a list of `(scope_path, AutodocConfig)` pairs. If none are found, returns `[(".", default_config)]`
- For each discovered scope, `load_autodoc_config(repo_path, scope_path)` reads and validates the `.autodoc.yaml` at that scope path (returns defaults if scope has no config file)
- The **`scan_file_tree` task** uses `include`/`exclude` patterns (relative to scope root) to physically prune excluded files within the scope directory and produce a `FileTree`
- The **StructureExtractor** receives the pre-computed `FileTree` for the scope's repository layout analysis
- The **PageGenerator** uses `style` settings to adjust prompt parameters (audience, tone, detail level)
- The **ReadmeDistiller** uses `readme` preferences for output formatting, including `output_path` for README placement relative to scope root
- The **PR creation task** collects all scope READMEs into a single PR, using `pull_request` settings for reviewers and auto-merge (PRs always target the repository's default branch)
- The `custom_instructions` string is injected verbatim into agent prompts, allowing users to provide project-specific terminology, preferences, and constraints

### Config Validation

The `load_autodoc_config` task performs strict validation when `.autodoc.yaml` is present (for each discovered scope):

- **Unknown keys** — Emit warnings (e.g., a typo `incldue:` instead of `include:` is flagged, not silently ignored)
- **Invalid values** — Fail with descriptive error (e.g., `audience: "beginner"` is not a valid option)
- **Type mismatches** — Fail with descriptive error (e.g., `include: "src/"` instead of `include: ["src/"]`)
- **Validation results** — Stored in the job record's `config_warnings` field so users can see if their config was applied correctly

### Fallback Behavior

When no `.autodoc.yaml` exists, sensible defaults are used (no warnings emitted):

- Include everything except common ignore patterns (node_modules, dist, build, __pycache__, .venv, vendor, coverage, .git)
- Audience: junior-developer
- Tone: tutorial
- Detail level: comprehensive
- README: output at `README.md` relative to scope root, unlimited length (`max_length: null`), include TOC, no badges
- PR: target repository's default branch, no auto-merge, no specific reviewers

### Config Schema

```
AutodocConfig:
    version: integer = 1
    include: list[string] = []          # Empty = all files included; non-empty = ONLY these paths
    exclude: list[string] = ["node_modules/", "dist/", "build/", ...]
    style: StyleConfig = defaults
    custom_instructions: optional string = null  # Free-form text injected into agent prompts
    readme: ReadmeConfig = defaults
    pull_request: PRConfig = defaults

ReadmeConfig:
    output_path: string = "README.md"   # Path relative to .autodoc.yaml location
    max_length: optional integer = null  # null = unlimited, integer = word cap
    include_toc: boolean = true
    include_badges: boolean = false
```

---

## 9. Database Design

### PostgreSQL + pgvector

The service uses PostgreSQL with pgvector as its single database, providing both document storage (via JSONB columns) and semantic search (via pgvector embedding columns). SQLAlchemy async with the asyncpg driver handles all database operations.

No abstract interfaces — the repositories are concrete classes. FastAPI's `Depends()` is used for dependency injection. The `domain/entities/` module contains Pydantic models for the API/service layer (validation and serialization), while `database/models.py` contains SQLAlchemy ORM models for database operations. Database repositories handle the mapping between them.

### Database Schema

- **`repositories`** table: id (UUID PK), provider (enum: github/bitbucket/gitlab), url (unique), org, name, default_branch, access_token_encrypted (nullable, write-only), created_at, updated_at
- **`jobs`** table: id (UUID PK), repository_id (FK), status (enum: pending/running/completed/failed/cancelled), mode (enum: full/incremental), branch, commit_sha, dry_run (boolean, default false), prefect_flow_run_id, app_commit_sha (string — git SHA of the autodoc application, read from `APP_COMMIT_SHA` env var at job creation time; set at Docker build time via CI `--build-arg` for prompt/rubric versioning and reproducibility), quality_report (JSONB — stores per-page scores, overall score, which pages required regeneration, README quality score), token_usage (JSONB — total_input_tokens, total_output_tokens, by_agent breakdown, estimated_cost_usd), config_warnings (JSONB array — validation warnings from .autodoc.yaml), callback_url (nullable string — webhook URL for job completion notification), error_message, pull_request_url, created_at, updated_at
- **`wiki_structures`** table: id (UUID PK), repository_id (FK), job_id (FK — provenance tracking), branch (string), scope_path (string — directory of the `.autodoc.yaml`, e.g., `"."` for root, `"packages/auth"` for a monorepo sub-project), version (integer — 1-based, max 3 per repository+branch+scope), title, description, sections (JSONB — the full hierarchy of sections with their page references), commit_sha (the SHA this structure was generated from), created_at, updated_at — Up to **3 versions** are retained per `(repository_id, branch, scope_path)`; when a new version is generated, the oldest beyond 3 is deleted
- **`wiki_pages`** table: id (UUID PK), wiki_structure_id (FK, **CASCADE DELETE** — when a wiki structure version is removed, all its pages and embeddings are automatically cleaned up), page_key (string, URL-friendly), title, description, importance (enum: high/medium/low), page_type (enum: api/module/class/overview), source_files (JSONB array of relative file paths), related_pages (JSONB array of page_key references), content (text — the generated markdown), content_embedding (vector — pgvector column for semantic search), quality_score (float), created_at, updated_at


### Database Indexes

- `wiki_pages.content`: GIN index using `to_tsvector('english', content)` for full-text search
- `wiki_pages.content_embedding`: HNSW index for pgvector semantic search (cosine distance)
- `wiki_structures`: Unique composite index on `(repository_id, branch, scope_path, version)` — allows up to 3 versions per `(repository_id, branch, scope_path)`

- `jobs`: Composite index on `(repository_id, status)` for job listing queries
- `jobs`: Index on `(repository_id, branch, mode, dry_run, status)` for idempotency checks

### Transaction Scope

Each Prefect task is the unit of transactional consistency. Database operations within a single task use a single `AsyncSession` and commit atomically. Cross-task consistency is managed by the flow's error handling — if a later task fails, earlier task commits persist (this is acceptable because Prefect can resume from the last successful task on retry).

### ADK Session Storage

ADK agent sessions (used to persist Generator conversation history across retry attempts in the Generator & Critic loop) are stored in PostgreSQL via ADK's `DatabaseSessionService`. The service is initialized with the same `DATABASE_URL` used for the application database:

```
session_service = DatabaseSessionService(db_url=DATABASE_URL)
```

ADK automatically creates and manages the session tables. Each Generator run creates a new session; session data includes the full conversation history (prior outputs + Critic feedback). Sessions are archived to S3 and deleted from PostgreSQL at the end of each flow run via the `archive_adk_sessions` task in the flow's `FINALLY` block (see Prefect Tasks).

### Embedding Configuration

- Embedding dimensions are configurable via `EMBEDDING_DIMENSIONS` env var (default: 768)
- `EMBEDDING_MODEL` env var specifies which model generates embeddings
- The `wiki_pages` table uses a pgvector column for per-page embeddings enabling semantic search through the MCP server
- **Breaking change**: Changing `EMBEDDING_MODEL` or `EMBEDDING_DIMENSIONS` between runs invalidates existing embeddings. A full re-generation of all repositories is required after changing embedding configuration. Semantic search results will be degraded until re-generation completes.

### Repository Implementation

```
CLASS WikiPageRepository:
    CONSTRUCTOR(session: AsyncSession):
        self.session = session

    ASYNC METHOD search_by_text(query, repository_id, branch, scope_path=None, limit=10) -> list[WikiPage]:
        // Full-text search across wiki page content using tsvector GIN index
        // JOIN wiki_pages with wiki_structures
        // WHERE wiki_structures.repository_id = repository_id
        // AND wiki_structures.branch = branch
        // AND (scope_path IS NULL OR wiki_structures.scope_path = scope_path)  // Optional scope filter
        // AND wiki_pages.content @@ plainto_tsquery('english', query)
        // ORDER BY ts_rank(to_tsvector('english', content), query)
        // LIMIT limit
        RETURN matching pages with rank

    ASYNC METHOD search_by_embedding(query_vector, repository_id, branch, limit=10) -> list[WikiPage]:
        // Semantic similarity search using pgvector HNSW index
        // JOIN wiki_pages with wiki_structures
        // WHERE wiki_structures.repository_id = repository_id
        // AND wiki_structures.branch = branch
        // ORDER BY cosine_distance(wiki_pages.content_embedding, query_vector)
        // LIMIT limit
        RETURN matching pages with distance score

    ASYNC METHOD search_hybrid(query, query_vector, repository_id, branch, limit=10, k=60) -> list[WikiPage]:
        // Reciprocal Rank Fusion (RRF) combining text and semantic search
        // 1. Run text search (2x limit candidates)
        text_results = AWAIT search_by_text(query, repository_id, branch, limit=limit*2)
        // 2. Run semantic search (2x limit candidates)
        semantic_results = AWAIT search_by_embedding(query_vector, repository_id, branch, limit=limit*2)
        // 3. Compute RRF score for each page: score = 1/(k + rank_text) + 1/(k + rank_semantic)
        //    where k=60 is a constant that controls how much lower-ranked results are penalized
        //    Pages absent from one result set use a large penalty rank (1000) instead of 0
        // 4. Sort by combined RRF score descending
        // 5. Return top `limit` results
        RETURN merged results with rrf_score
```

### Dual Output

The service produces two output formats:

**A. Structured Wiki** — the tree-like structure of sections and pages:
- Stored in PostgreSQL (`wiki_structures` + `wiki_pages` tables)
- Serves web display through the API
- Supports full-text search (PostgreSQL tsvector) and semantic search (pgvector) via both API and MCP
- Pages may contain overlapping/duplicate information across pages — this is intentional, each page should be self-contained

**B. Distilled README.md** — a single comprehensive markdown file per scope:
- Generated from all wiki pages within the scope by the ReadmeDistiller agent
- **Not stored in the database** — exists only in the repository via pull request
- Placed at `{scope_path}/{readme.output_path}` (configurable via `.autodoc.yaml`, defaults to `README.md`)
- Pushed to the repository via pull request (all scope READMEs in a single PR)
- README quality score is included in the job's `quality_report` JSONB field
- Eliminates all redundancy into one cohesive document

---

## 10. API Design

### Authentication

API-level authentication and authorization are handled at the deployment infrastructure layer (reverse proxy, API gateway, or cloud load balancer), not within the application. The application trusts all incoming requests. This simplifies the application but requires appropriate infrastructure configuration (VPN, API gateway auth, network policies) in production deployments.

### Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/repositories` | Register a repository (with optional access_token) |
| `GET` | `/repositories` | List registered repositories (cursor pagination) |
| `GET` | `/repositories/{id}` | Get repository details |
| `PATCH` | `/repositories/{id}` | Update repository (default_branch, access_token) |
| `DELETE` | `/repositories/{id}` | Delete repository and all associated docs, jobs |
| `POST` | `/webhooks/push` | Receive Git provider push/merge webhooks, trigger incremental generation |
| `POST` | `/jobs` | Trigger documentation generation (idempotent, supports dry_run) |
| `GET` | `/jobs` | List jobs with filtering (cursor pagination, proxies Prefect) |
| `GET` | `/jobs/{id}` | Check job status (includes quality_report, token_usage, pull_request_url) |
| `GET` | `/jobs/{id}/structure` | Get extracted wiki structure |
| `GET` | `/jobs/{id}/tasks` | Get Prefect task states for progress tracking |
| `GET` | `/jobs/{id}/logs` | Get Prefect flow logs |
| `POST` | `/jobs/{id}/cancel` | Cancel a PENDING or RUNNING job |
| `POST` | `/jobs/{id}/retry` | Retry a FAILED job (resumes from last successful task) |
| `GET` | `/documents/{repo_id}?branch=main&scope=.` | Get structured wiki — sections + pages (cursor pagination) |
| `GET` | `/documents/{repo_id}/pages/{page_key}?branch=main&scope=.` | Get a single wiki page |

| `GET` | `/documents/{repo_id}/search?branch=main&scope=.` | Search wiki pages (text, semantic, or hybrid via RRF) |
| `GET` | `/documents/{repo_id}/scopes?branch=main` | List all documentation scopes for a repository |
| `GET` | `/health` | Health check (dependency status) |

### Health Check

`GET /health` returns dependency status for all critical and non-critical services:

```
HealthResponse:
    status: string                   # "healthy" | "degraded" | "unhealthy"
    dependencies:
        database: DependencyStatus   # PostgreSQL connectivity
        prefect: DependencyStatus    # Prefect server API reachability
        otel: DependencyStatus       # OpenTelemetry exporter status
    timestamp: datetime

DependencyStatus:
    status: string                   # "ok" | "error"
    details: optional string         # Error message if status is "error"
    latency_ms: optional float       # Response time
```

Overall `status` is `healthy` only if all dependencies pass, `degraded` if non-critical dependencies (OTel) fail, `unhealthy` if critical dependencies (database, Prefect) fail.

### Pagination

All list endpoints use cursor-based pagination with a consistent format:

```
// Request query parameters
?cursor=<opaque_string>&limit=20

// Response wrapper
PaginatedResponse[T]:
    items: list[T]
    next_cursor: optional string     # null if no more results
    limit: integer
```

### Webhook Receiver

`POST /webhooks/push` receives push/merge webhooks from Git providers (GitHub, GitLab, Bitbucket) and automatically triggers incremental documentation generation. Each provider sends a different payload format; the endpoint normalizes them to extract the repository URL, branch, and commit SHA.

```
// POST /webhooks/push
// Accepts GitHub push events, GitLab push events, Bitbucket push events
// Provider is detected from request headers (X-GitHub-Event, X-Gitlab-Event, etc.)

WebhookPushHandler:
    1. Detect provider from headers
    2. Parse provider-specific payload → extract (repo_url, branch, commit_sha)
    3. Skip if branch is not the repository's default branch
    4. Resolve repo_url to repository_id (auto-register if needed)
    5. Trigger POST /jobs internally (mode: incremental, idempotent)
    6. Return 202 Accepted with job_id
```

**Security**: Webhook signature verification (GitHub HMAC-SHA256, GitLab token header, Bitbucket IP allowlist) is recommended but deferred to implementation — depends on deployment context. A per-repository `webhook_secret` field may be added to the `repositories` table.

### Idempotency

`POST /jobs` is idempotent: if a job for the same `(repository_id, branch, mode, dry_run)` is already PENDING or RUNNING, the existing job is returned instead of creating a duplicate. This prevents accidental double-submission from client retries or UI double-clicks. The `dry_run` flag is part of the idempotency key so that a dry-run job never collides with a real generation job. The webhook handler benefits from this — rapid successive pushes to the same branch won't create duplicate jobs.

### Request/Response Schemas

```
// POST /repositories
RegisterRepositoryRequest:
    url: string                      # Git repository URL
    provider: string                 # "github" | "bitbucket" | "gitlab"
    default_branch: string = "main"
    access_token: optional string    # Write-only, encrypted at rest

RepositoryResponse:
    id: UUID
    url: string
    provider: string
    org: string
    name: string
    default_branch: string
    created_at: datetime
    // Note: access_token is NEVER returned

// PATCH /repositories/{id}
UpdateRepositoryRequest:
    default_branch: optional string  # Update the default branch
    access_token: optional string    # Update the encrypted access token (write-only)
// Returns RepositoryResponse

// DELETE /repositories/{id}
// Cascading delete: removes all associated wiki_structures, wiki_pages, and jobs
// Returns 204 No Content

// POST /jobs
CreateJobRequest:
    repository_id: UUID
    branch: string = "main"
    mode: string = "full"            # "full" | "incremental"
    dry_run: boolean = false         # If true, only extract structure (no generation)
    callback_url: optional string    # Webhook URL for job completion/failure notification

JobResponse:
    id: UUID
    repository_id: UUID
    status: string                   # pending | running | completed | failed | cancelled
    mode: string
    branch: string
    dry_run: boolean
    quality_report: optional dict    # Per-page scores, overall score, regeneration info, README score
    token_usage: optional dict       # {total_input_tokens, total_output_tokens, by_agent, estimated_cost_usd}
    config_warnings: optional list   # Warnings from .autodoc.yaml validation
    pull_request_url: optional string
    error_message: optional string
    created_at: datetime

// GET /jobs?repository_id=...&status=...&cursor=...&limit=20
// Returns PaginatedResponse[JobResponse]
// Filters: repository_id (optional UUID), status (optional enum), branch (optional string)
// Note: Prefect UI (http://localhost:4200) provides richer ops-level monitoring of flow runs.
// This endpoint is a lightweight API proxy for programmatic consumers.

// GET /documents/{repo_id}/search?query=...&search_type=hybrid&limit=10&branch=main&scope=.
// All document endpoints accept optional `branch` (defaults to repository's default_branch)
// and `scope` (defaults to "." for root scope) query parameters.
// Omitting `scope` searches across all scopes for the given branch.
SearchResponse:
    results: list[SearchResult]
    total: integer
    search_type: string              # The search type that was used

SearchResult:
    page_key: string
    title: string
    snippet: string                  # Relevant excerpt
    score: float                     # Relevance score (RRF score for hybrid, rank for text, distance for semantic)
```

### Webhook Callbacks

When `callback_url` is provided in `CreateJobRequest`, the service POSTs a notification on job completion or failure:

```
// POST to callback_url
WebhookPayload:
    job_id: UUID
    status: string                   # completed | failed | cancelled
    repository_id: UUID
    branch: string
    pull_request_url: optional string
    quality_report: optional dict
    token_usage: optional dict
    error_message: optional string
    completed_at: datetime
```

### Hybrid Search Algorithm

The `search_type=hybrid` option uses **Reciprocal Rank Fusion (RRF)** to combine text and semantic search results:

1. Run full-text search (PostgreSQL tsvector) — returns ranked results
2. Run semantic search (pgvector cosine distance) — returns ranked results
3. For each page appearing in either result set, compute RRF score: `score = 1/(k + rank_text) + 1/(k + rank_semantic)` where `k=60`
4. Pages appearing in only one result set receive `1/(k + rank)` for that set and `1/(k + 1000)` (large penalty rank) for the other — this avoids heavily penalizing strong single-set matches while still favoring dual-set matches
5. Sort by combined RRF score descending, return top `limit` results

---

## 11. MCP Integration

### Consuming External MCP Servers

The agents consume external MCP servers for filesystem and git operations via ADK's `McpToolset`:

```
filesystem_toolset = McpToolset(
    connection = StdioConnection(command="npx", args=["-y", "@anthropic/mcp-filesystem"]),
    tool_filter = ["read_file", "list_directory", "read_multiple_files"]
)
```

### Exposing Agents as MCP Server

The autodoc MCP server exposes three tools. All tools accept `repo_url` as input for external agent convenience. Internally, the MCP server resolves `repo_url` to a `repository_id` via a database lookup. If the repository is not yet registered, the MCP server auto-registers it before proceeding:

```
// Internal MCP helper — resolves repo_url to repository_id
ASYNC METHOD resolve_repository(repo_url, provider=None) -> UUID:
    repo = AWAIT repository_service.find_by_url(repo_url)
    IF repo:
        RETURN repo.id
    // Auto-register if not found
    provider = provider OR detect_provider_from_url(repo_url)
    repo = AWAIT repository_service.create(url=repo_url, provider=provider)
    RETURN repo.id
```

**generate_documentation** — Trigger documentation generation for a repository

```
Tool: generate_documentation
Input:
    repo_url: string (required)      # Git repository URL to document
    branch: string = "main"          # Branch to document
    mode: string = "full"            # "full" | "incremental"
Output:
    job_id: string                   # Job ID for status polling
```

**extract_structure** — Extract documentation structure without generating pages

```
Tool: extract_structure
Input:
    repo_url: string (required)      # Git repository URL to analyze
    branch: string = "main"          # Branch to analyze
Output:
    structure: PageStructure         # Extracted documentation structure
```

**search_documentation** — Search across generated documentation

```
Tool: search_documentation
Input:
    repo_url: string (required)      # Repository URL to search docs for
    query: string (required)           # Search query (natural language or keywords)
    search_type: string = "hybrid"     # "text" | "semantic" | "hybrid"
    limit: integer = 10                # Max results to return
Output:
    results: list[SearchResult]        # Matching documentation pages with snippets
```

---

## 12. Repository Authentication

The service supports private repositories on GitHub, Bitbucket, and GitLab. Authentication tokens are used for both cloning private repos and creating pull requests.

### Supported Auth Methods

- **GitHub**: Personal Access Token (PAT) or GitHub App installation token
- **Bitbucket**: App password or OAuth consumer token
- **GitLab**: Personal access token or deploy token

### Token Storage

- Encrypted at rest in the `repositories` table (`access_token_encrypted` column)
- Never included in API responses (write-only field)
- Injected into clone URLs at runtime: `https://{token}@github.com/org/repo.git`

### Environment-Level Defaults

Used when no per-repo token is configured:

```env
GITHUB_DEFAULT_TOKEN=ghp_...
BITBUCKET_DEFAULT_TOKEN=...
GITLAB_DEFAULT_TOKEN=glpat-...
TOKEN_ENCRYPTION_KEY=...          # For encrypting stored tokens
```

### API Changes

- `POST /repositories` accepts an optional `access_token` field in the request body
- The access token is encrypted before storage and never returned in responses
- All repository response schemas exclude the token field

### Clone Authentication

```
TASK clone_repository(repo_url, branch, job_id, access_token=None) -> (string, string):
    repo_path = create_temp_dir(prefix="autodoc_{job_id}_")

    clone_url = repo_url
    IF access_token:
        // Inject token into URL
        parsed = parse_url(repo_url)
        clone_url = "{parsed.scheme}://{access_token}@{parsed.host}{parsed.path}"

    git_clone(url=clone_url, to_path=repo_path, branch=branch, depth=1)
    commit_sha = git_rev_parse("HEAD", cwd=repo_path)
    RETURN (repo_path, commit_sha)
```

### PR Creation Auth

The same token is used for creating PRs via the provider's REST API:

- GitHub: `POST /repos/{owner}/{repo}/pulls` with `Authorization: Bearer {token}`
- Bitbucket: `POST /2.0/repositories/{workspace}/{repo}/pullrequests` with `Authorization: Bearer {token}`

### PR Creation Details

- Branch name: `autodoc/{repo_name}-{branch}-{job_id_short}-{YYYY-MM-DD}` — distinguished to avoid collisions across repositories, branches, and concurrent jobs (e.g., `autodoc/my-api-main-a1b2c3-2026-02-10`)
- PR target: always the repository's **default branch** (as registered in the `repositories` table)
- Commit message: `docs: update auto-generated technical documentation`
- Commit includes: all scope README files, each placed at `{scope_path}/{readme.output_path}` (e.g., `README.md` for root scope, `packages/auth/README.md` for a sub-project scope)
- PR title: `Update technical documentation`
- PR body: minimal summary — number of scopes processed, total pages generated/updated, overall quality score, and a link to `GET /jobs/{id}` for detailed per-page breakdown. A note that this was auto-generated.
- Uses the repository's stored access token for authentication
- Respects `.autodoc.yaml` PR preferences (`reviewers`, `auto_merge`) if configured — uses the root scope's PR settings if multiple scopes exist
- **Stale PR cleanup**: Before creating a new PR, `close_stale_autodoc_prs` searches for open PRs with the `autodoc/` branch prefix targeting the same base branch, closes them with a comment, and deletes the stale branches

---

## 13. Operations & Observability

### OpenTelemetry / ADK Tracing

Google ADK has built-in OpenTelemetry support that automatically generates spans for agent execution, LLM calls, and tool usage. A `TracerProvider` is configured at application startup before any ADK imports. `LoggingInstrumentor` injects `trace_id` and `span_id` into all structured log entries for end-to-end correlation:

```
// Configure at startup (before importing ADK agents)
from opentelemetry.instrumentation.logging import LoggingInstrumentor

provider = TracerProvider()

// External exporter (optional — for Jaeger, OTLP collector, etc.)
IF OTEL_EXPORTER_OTLP_ENDPOINT:
    external_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT))
    provider.add_span_processor(external_processor)

trace.set_tracer_provider(provider)

// Inject trace_id and span_id into all log records
LoggingInstrumentor().instrument(set_logging_format=True)
```

**What gets traced automatically by ADK:**
- Agent execution spans (state, delegation, execution flow)
- LLM call spans (model, input/output tokens, latency)
- Tool execution spans (tool name, parameters, results)
- Error spans (exceptions, error states)

**Token usage and quality metrics** are not collected from spans. Instead, each `AgentResult` carries a `token_usage` field populated by the agent during execution. The flow aggregates these metrics from all `AgentResult` instances into the job's `token_usage` and `quality_report` fields via `aggregate_job_metrics()`. This avoids in-process span storage and its associated memory concerns.

### Prefect UI for Ops Monitoring

The Prefect UI (`http://localhost:4200`) serves as the primary ops dashboard for monitoring:
- Flow run listing with filtering by state, deployment, tags
- Task-level progress within each flow run
- Retry history and failure diagnostics
- Scheduling and concurrency visualization

The `GET /jobs` API endpoint provides a lightweight proxy for programmatic consumers (frontends, MCP clients, CI/CD integrations) who don't have direct access to the Prefect UI.

### Startup Reconciliation

On application startup, a reconciliation routine scans the `jobs` table for records stuck in `RUNNING` status. For each, it checks the corresponding Prefect flow run state. If the flow is no longer active (completed, failed, cancelled, or missing), the job status is updated accordingly. This handles cases where a Prefect worker crashed or was terminated during job execution. Prefect 3's native `SIGTERM` handling provides graceful shutdown for in-flight tasks; this reconciliation catches anything that fell through.

### Temp Directory Cleanup

A startup routine and/or scheduled task scans the system temp directory for `autodoc_*` directories older than 1 hour and removes them. This handles cases where the Prefect worker crashes before the `finally` block in the flow runs:

```
TASK cleanup_orphaned_repos(max_age_hours=1) -> integer:
    count = 0
    FOR path IN glob(temp_dir / "autodoc_*"):
        age_hours = (now - last_modified(path)) / 3600
        IF age_hours > max_age_hours:
            remove_directory(path)
            count += 1
    RETURN count
```

### Structured Logging

All log entries include:

- `job_id` — propagated through all tasks as a correlation ID
- `agent_name` — which agent produced the log
- `task_name` — which Prefect task is running
- JSON format for machine parseability
- OpenTelemetry `trace_id` and `span_id` for correlation with OTel traces

### Quality Metrics

The following metrics are aggregated from all `AgentResult` instances by `aggregate_job_metrics()` and stored in the Job's `quality_report` JSONB field (accessible via `GET /jobs/{id}`):

- Average page quality score per job
- README quality score
- Regeneration rate (what percentage of pages needed retries)
- Time per page generation
- Total job duration
- Pages below minimum floor (per job)
- Per-page evaluation history (all attempts, scores, feedback)

### Token Usage & Cost Tracking

The `aggregate_job_metrics()` function collects LLM usage from all `AgentResult.token_usage` fields and stores in the Job's `token_usage` JSONB field:

```
token_usage:
    total_input_tokens: integer
    total_output_tokens: integer
    by_agent:                        # Breakdown per agent type
        structure_extractor: {input_tokens, output_tokens}
        structure_critic: {input_tokens, output_tokens}
        page_generator: {input_tokens, output_tokens}
        page_critic: {input_tokens, output_tokens}
        readme_distiller: {input_tokens, output_tokens}
        readme_critic: {input_tokens, output_tokens}
    total_llm_calls: integer
    estimated_cost_usd: float
```

### API Rate Limiting

API-level rate limiting is handled at the reverse proxy layer (NGINX or cloud load balancer), not in the application. No application-level rate limiting middleware is needed.

### Per-Agent Model Configuration

Each agent's Generator and Critic can be configured with different models, enabling the use of a separate Critic model to avoid self-reinforcing evaluation bias:

```env
# Generator models
STRUCTURE_EXTRACTOR_MODEL=gemini-2.0-flash
PAGE_GENERATOR_MODEL=gemini-2.0-flash
README_DISTILLER_MODEL=gemini-2.0-flash

# Critic models (can differ from generators to avoid self-evaluation bias)
STRUCTURE_CRITIC_MODEL=gemini-2.0-flash
PAGE_CRITIC_MODEL=gemini-2.0-flash
README_CRITIC_MODEL=gemini-2.0-flash
```

```
AgentSettings:
    structure_extractor_model: string = "gemini-2.0-flash"
    structure_critic_model: string = "gemini-2.0-flash"
    page_generator_model: string = "gemini-2.0-flash"
    page_critic_model: string = "gemini-2.0-flash"
    readme_distiller_model: string = "gemini-2.0-flash"
    readme_critic_model: string = "gemini-2.0-flash"
```

### Deferred Implementation Concerns

The following concerns are acknowledged as important but deferred to the implementation phase, as they are highly iterative and best developed with real test data:

- **Context window management** — Per-agent token budgets, truncation strategies for oversized inputs (large file trees, many source files), chunking for the ReadmeDistiller's all-pages input. This is a critical concern that must be addressed during implementation.
- **Prompt design** — System prompt structure for Generator vs. Critic, how `.autodoc.yaml` style/custom_instructions/audience settings are injected, how Critic feedback is formatted as retry prompts.
- **Webhook security** — HMAC signature validation, webhook secrets, minimal payload strategies. Depends on deployment context and client requirements.
- **Testing strategy details** — Mocking strategy for agents without real LLM calls, Critic calibration tests, golden file tests, database fixtures, CI integration test flow.
- **Scheduled/periodic documentation runs** — The system supports on-demand triggers only. For automated updates, integrate with CI/CD pipelines (GitHub Actions, GitLab CI, etc.) to call `POST /jobs` on push/merge events. Native Prefect scheduling may be added in a future iteration.

---

## 14. Testing Strategy

### ADK WebUI Testing

```bash
# Test individual agents in isolation
adk web src/agents/structure_extractor
adk web src/agents/page_generator
adk web src/agents/readme_distiller
```

### Prefect Flow Testing

```
TEST test_documentation_flow_success:
    WITH prefect_test_harness:
        result = AWAIT documentation_flow(
            job_id="test-123",
            repository_id="repo-uuid-123",
            branch="main"
        )

        ASSERT result IS NOT NONE
        ASSERT "pages" IN result
        ASSERT "readme" IN result
        ASSERT "pr_url" IN result

TEST test_incremental_flow_no_changes:
    WITH prefect_test_harness:
        result = AWAIT incremental_update_flow(
            job_id="test-incr-123",
            repository_id="repo-uuid-123",
            branch="main"
        )

        ASSERT result["status"] == "no_changes"
```

### Agent Testing

```
TEST test_structure_extractor_generator_critic_loop:
    // Verify agent runs Generator + Critic loop and returns AgentResult
    agent = StructureExtractorAgent(generator_model="test-model", critic_model="test-model", ...)
    agent_result = AWAIT agent.run(StructureInput(repo_path="/test/repo", file_tree=mock_file_tree))

    ASSERT agent_result IS AgentResult
    ASSERT agent_result.output IS PageStructure
    ASSERT agent_result.output.pages IS NOT EMPTY
    ASSERT agent_result.evaluation_history IS NOT EMPTY

TEST test_page_generator_below_floor:
    // Verify agent flags results below minimum quality floor
    agent = PageGeneratorAgent(generator_model="test-model", critic_model="test-model", threshold=7.0, max_attempts=1, ...)
    agent_result = AWAIT agent.run(page_spec)

    // Result should still be returned (best attempt) even if below threshold
    ASSERT agent_result.output IS GeneratedPage
    ASSERT agent_result.below_minimum_floor IS TRUE OR FALSE  // depends on Critic score
```

### API Testing

```bash
pytest tests/integration/test_api/ -v
pytest tests/integration/test_agents/ -v
pytest tests/integration/test_workflows/ -v
```

---

## 15. Deployment

### Docker Images — Three-Tier Separation

Three distinct Docker images serve different roles with different dependency footprints:

| Image | Dockerfile | Contents | Size |
|-------|-----------|----------|------|
| **API Service** | `Dockerfile` | FastAPI + Prefect client + SQLAlchemy — no AI/ML libraries | Lightweight |
| **Prefect Worker** | Uses official `prefecthq/prefect:3-latest` | Prefect worker only — dispatcher, does not run flow code | Lightweight |
| **Flow Runner** | `Dockerfile.flow` | Flow code + AI libraries (ADK, LLM SDKs) + git tools + all dependencies | Heavy |

In production (Kubernetes), the worker dispatches flow runs to pods using the **Flow Runner** image. In local development (process pool), the worker runs flows as subprocesses using the developer's local Python environment — the Flow Runner image is not needed locally.

### CI Pipeline for Flow Images

Flow code is baked into the Docker image rather than pulled from git at runtime:

1. Flow code lives in the same repository as the API service
2. On merge to main, CI builds the Flow Runner image (`Dockerfile.flow`) and pushes to the container registry (ECR on EKS)
3. The image is tagged with the git commit SHA for reproducibility: `autodoc-flow:{commit_sha}`
4. Prefect deployment is updated to reference the new image tag
5. The `app_commit_sha` field in the `jobs` table is populated from the `APP_COMMIT_SHA` environment variable, which is set at build time in the Docker image (e.g., `ARG APP_COMMIT_SHA` in Dockerfile, injected by CI via `--build-arg`)

This ensures:
- Pods are fully self-contained — no runtime dependency on GitHub availability
- No startup latency from cloning flow code
- Reproducible: the image tag pins the exact code version (matching `app_commit_sha` for prompt/rubric versioning)

### Docker Compose — Full Stack (Quick Start & CI)

```yaml
# docker-compose.yml — full stack: run everything with `docker compose up`
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: autodoc
      POSTGRES_PASSWORD: autodoc
      POSTGRES_DB: autodoc
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./deployment/scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql

  prefect-server:
    image: prefecthq/prefect:3-latest
    command: prefect server start --host 0.0.0.0
    ports:
      - "4200:4200"
    environment:
      PREFECT_SERVER_API_HOST: "0.0.0.0"
      PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://autodoc:autodoc@postgres:5432/prefect"
    depends_on:
      - postgres

  prefect-worker:
    build:
      context: .
      dockerfile: Dockerfile.flow
    command: >
      /bin/sh -c "prefect work-pool create local-dev --type process --overwrite
      && prefect worker start --pool local-dev"
    environment:
      PREFECT_API_URL: "http://prefect-server:4200/api"
      DATABASE_URL: "postgresql+asyncpg://autodoc:autodoc@postgres:5432/autodoc"
    depends_on:
      - prefect-server
      - postgres

  api:
    build: .
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: "postgresql+asyncpg://autodoc:autodoc@postgres:5432/autodoc"
      PREFECT_API_URL: "http://prefect-server:4200/api"
      PREFECT_WORK_POOL: "local-dev"
      AUTODOC_FLOW_DEPLOYMENT_PREFIX: "dev"
    depends_on:
      - postgres
      - prefect-server

volumes:
  postgres_data:
```

Note: Prefect Server uses its own database (`prefect`) on the same PostgreSQL instance, separate from the application database (`autodoc`). The `init-db.sql` script (mounted via `docker-entrypoint-initdb.d`) creates the `prefect` database on first PostgreSQL startup (`CREATE DATABASE prefect;`). In production, these may be separate PostgreSQL instances.

### Docker Compose — Dev Infrastructure Only (Hybrid Mode)

```yaml
# docker-compose.dev.yml — infrastructure only: Server + PostgreSQL
# Worker and API run natively for fast iteration and debugging
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: autodoc
      POSTGRES_PASSWORD: autodoc
      POSTGRES_DB: autodoc
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./deployment/scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql

  prefect-server:
    image: prefecthq/prefect:3-latest
    command: prefect server start --host 0.0.0.0
    ports:
      - "4200:4200"
    environment:
      PREFECT_SERVER_API_HOST: "0.0.0.0"
      PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://autodoc:autodoc@postgres:5432/prefect"
    depends_on:
      - postgres

volumes:
  postgres_data:
```

### Makefile

```makefile
# Standard developer workflow:
#   Option A (all Docker):  make up
#   Option B (hybrid):      make dev-up, then make worker and make api in separate terminals

# --- Full Docker Stack ---
up:                                     ## Start all services (Docker)
	docker compose up -d

down:                                   ## Stop all services
	docker compose down

logs:                                   ## Tail all service logs
	docker compose logs -f

# --- Hybrid Mode (infra in Docker, worker + API native) ---
dev-up:                                 ## Start infrastructure only (Prefect Server + PostgreSQL)
	docker compose -f docker-compose.dev.yml up -d

dev-down:                               ## Stop infrastructure
	docker compose -f docker-compose.dev.yml down

worker:                                 ## Start local process worker (native)
	PREFECT_API_URL=http://localhost:4200/api prefect worker start --pool local-dev

api:                                    ## Start FastAPI with hot reload (native)
	PREFECT_API_URL=http://localhost:4200/api uvicorn src.api.main:app --reload --port 8080

# --- Deployment & Setup ---
deploy-local:                           ## Register flow deployments against local work pool
	prefect work-pool create local-dev --type process --overwrite
	PREFECT_API_URL=http://localhost:4200/api prefect deploy --all

migrate:                                ## Run database migrations
	alembic upgrade head

# --- Testing ---
test:                                   ## Run all tests
	pytest tests/ -v

test-unit:                              ## Run unit tests only
	pytest tests/unit/ -v

test-integration:                       ## Run integration tests
	pytest tests/integration/ -v
```

---

## 16. Environment Configuration

```bash
# .env.example

# Database (PostgreSQL + pgvector)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/autodoc
DB_POOL_SIZE=10                        # Base connection pool size
DB_POOL_MAX_OVERFLOW=20                # Additional connections allowed beyond pool_size
DB_POOL_TIMEOUT=30                     # Seconds to wait for a connection from pool

# Embeddings
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_DIMENSIONS=768

# Prefect
PREFECT_API_URL=http://localhost:4200/api
PREFECT_WORK_POOL=local-dev                    # local-dev (process) for dev, k8s-pool (kubernetes) for production
AUTODOC_FLOW_DEPLOYMENT_PREFIX=dev             # dev or prod — selects deployment target (dev/documentation, prod/documentation)

# MCP
MCP_FILESYSTEM_ENABLED=true
MCP_GIT_ENABLED=true

# Agent Generator Models (per-agent configuration)
STRUCTURE_EXTRACTOR_MODEL=gemini-2.0-flash
PAGE_GENERATOR_MODEL=gemini-2.0-flash
README_DISTILLER_MODEL=gemini-2.0-flash

# Agent Critic Models (can differ from generators to avoid self-evaluation bias)
STRUCTURE_CRITIC_MODEL=gemini-2.0-flash
PAGE_CRITIC_MODEL=gemini-2.0-flash
README_CRITIC_MODEL=gemini-2.0-flash

# Quality Gates
STRUCTURE_EVAL_THRESHOLD=7.0
PAGE_EVAL_THRESHOLD=7.0
README_EVAL_THRESHOLD=7.0
MINIMUM_SCORE_FLOOR=4.0
MAX_REGENERATION_ATTEMPTS=3
BACKOFF_BASE_SECONDS=2.0

# Repository Authentication
GITHUB_DEFAULT_TOKEN=
BITBUCKET_DEFAULT_TOKEN=
GITLAB_DEFAULT_TOKEN=
TOKEN_ENCRYPTION_KEY=

# Per-Agent Per-Criterion Minimum Scores (optional, prevents masking critical failures)
# PageGenerator criterion floors
PAGE_ACCURACY_CRITERION_FLOOR=5.0
PAGE_COMPLETENESS_CRITERION_FLOOR=4.0
# StructureExtractor criterion floors
STRUCTURE_COVERAGE_CRITERION_FLOOR=5.0
# ReadmeDistiller criterion floors
README_COHERENCE_CRITERION_FLOOR=5.0

# Repository Size Limits
MAX_TOTAL_FILES=10000              # Fail if file count exceeds after pruning
MAX_FILE_SIZE=1048576              # Skip files larger than 1MB
MAX_REPO_SIZE=2147483648           # Fail if repo exceeds 2GB at clone time

# Concurrency
MAX_CONCURRENT_PAGE_GENERATIONS=5

# Session Archive (S3)
SESSION_ARCHIVE_BUCKET=autodoc-sessions

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces

# Application Version (set at Docker build time via --build-arg, used for app_commit_sha in jobs table)
APP_COMMIT_SHA=                            # Git SHA of the autodoc application — injected by CI into Flow Runner image

# API
API_HOST=0.0.0.0
API_PORT=8080
```

---

## 17. Sources

This design was informed by research from:

- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [Google ADK Samples Repository](https://github.com/google/adk-samples)
- [Google ADK Observability / OpenTelemetry](https://google.github.io/adk-docs/observability/)
- [Multi-Agent Patterns in ADK](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Prefect Documentation](https://docs.prefect.io/)
- [Prefect Flows and Tasks](https://docs.prefect.io/latest/concepts/flows/)
- [Prefect REST API — Flow Runs](https://docs.prefect.io/v3/api-ref/rest-api/server/flow-runs/read-flow-runs)
- [Prefect Self-Hosted Docker Compose](https://docs.prefect.io/v3/how-to-guides/self-hosted/docker-compose)
- [Prefect Task Runners](https://docs.prefect.io/3.0/develop/task-runners)
- [Prefect Kubernetes Infrastructure](https://docs.prefect.io/v3/deploy/infrastructure-examples/kubernetes)
- [Prefect Local Process Flows](https://docs.prefect.io/v3/how-to-guides/deployment_infra/run-flows-in-local-processes)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Reciprocal Rank Fusion (RRF)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
