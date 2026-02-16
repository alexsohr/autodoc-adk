# Research: AutoDoc ADK Documentation Generator

**Date:** 2026-02-15
**Purpose:** Technology pattern research for implementation decisions
**Stack:** Google ADK, Prefect 3, PostgreSQL/pgvector, FastAPI, SQLAlchemy async, OpenTelemetry

---

## 1. Google ADK DatabaseSessionService Configuration

**Decision**: Use `DatabaseSessionService` with PostgreSQL via asyncpg driver, with explicit session lifecycle management (create per flow run, use across Generator/Critic retries, archive to S3, then delete).

**Rationale**: DatabaseSessionService is ADK's built-in persistence layer for sessions. It uses SQLAlchemy under the hood and supports PostgreSQL natively. PostgreSQL is already the project's primary datastore, so reusing it for session persistence avoids adding infrastructure. The async driver requirement aligns with ADK's fully async architecture.

**Alternatives Considered**:
- **InMemorySessionService** — Default in ADK, but sessions are lost on restart. Unsuitable for Prefect tasks that may retry across process boundaries.
- **VertexAISessionService** — Google Cloud managed option. Adds vendor lock-in and external dependency; not needed when self-hosting PostgreSQL.
- **SQLite** — Supported but has concurrency limitations (write locking) that make it unsuitable for production with parallel page generation.

**Key Implementation Notes**:

```python
from google.adk.sessions import DatabaseSessionService

# Connection string format for PostgreSQL with asyncpg
db_url = "postgresql+asyncpg://user:password@localhost:5432/autodoc"

session_service = DatabaseSessionService(db_url=db_url)
```

- **Async driver required**: Must use `postgresql+asyncpg://` (not `postgresql://` or `psycopg2`). ADK enforces async-only database drivers. Note: there is an open issue (google/adk-python#1750) regarding synchronous psycopg2 dependency — asyncpg is the recommended path.
- **Timezone awareness**: Be aware of issue google/adk-python#4366 — timezone-aware datetime objects vs TIMESTAMP columns. Ensure PostgreSQL columns use `TIMESTAMP WITH TIME ZONE` or normalize datetimes to UTC naive.
- **Schema auto-creation**: DatabaseSessionService creates tables automatically on first initialization (`sessions`, `raw_events`, `app_state`, `user_state`).
- **Schema migration**: ADK v1.22.0 introduced a schema change. Pin ADK version and follow migration guide when upgrading.
- **Session lifecycle for AutoDoc flows**:
  1. **Create**: At flow start, call `session_service.create_session(app_name="autodoc", user_id=job_id)` — use `job_id` as the user_id to scope sessions per job.
  2. **Use**: Pass session to `Runner` for Generator/Critic loop. Conversation history accumulates across retries, allowing the Critic's feedback to be visible to the Generator on retry.
  3. **Archive**: After flow completion, export session data (events, state) to S3 as JSON for audit trail.
  4. **Delete**: Call `await session_service.delete_session(app_name="autodoc", user_id=job_id, session_id=session.id)` to clean up PostgreSQL.
- **Session listing**: Use `await session_service.list_sessions(app_name="autodoc", user_id=job_id)` to recover sessions after crash/restart.
- **Connect args**: For custom PostgreSQL schema, pass `connect_args={"options": "-c search_path=autodoc_sessions"}`.

**Sources**:
- [ADK Sessions Documentation](https://google.github.io/adk-docs/sessions/session/)
- [DatabaseSessionService Source (v1.17.0)](https://github.com/google/adk-python/blob/v1.17.0/src/google/adk/sessions/database_session_service.py)
- [ADK Masterclass Part 6: Persisting Sessions](https://saptak.in/writing/2025/05/10/google-adk-masterclass-part6)
- [Google Cloud Blog: Agent State and Memory](https://cloud.google.com/blog/topics/developers-practitioners/remember-this-agent-state-and-memory-with-adk)

---

## 2. Google ADK LlmAgent Generator & Critic Pattern

**Decision**: Use ADK's `LoopAgent` with two `LlmAgent` sub-agents (Generator + Critic) per agent module. The Critic signals completion via the `exit_loop` tool (setting `escalate=True`), and feedback flows through session conversation history. Each agent module (StructureExtractor, PageGenerator, ReadmeDistiller) instantiates its own LoopAgent.

**Rationale**: ADK's LoopAgent is purpose-built for the Generator-Critic pattern. It iterates sub-agents sequentially until either `max_iterations` is reached or a sub-agent calls `exit_loop`. Conversation history in the session provides natural feedback: the Critic's evaluation response is visible to the Generator on the next iteration, eliminating the need for manual state passing. Using separate LlmAgent instances allows different models (e.g., `PAGE_GENERATOR_MODEL` vs `PAGE_CRITIC_MODEL`) to avoid self-reinforcing bias.

**Alternatives Considered**:
- **Single LlmAgent with self-evaluation prompt** — Simpler but prone to self-reinforcing bias. The same model tends to rate its own output highly.
- **Custom agent loop (manual Python)** — More flexible but loses ADK's built-in session management, telemetry, and event tracking. Reimplements what LoopAgent already provides.
- **SequentialAgent without loop** — No retry mechanism. A single pass without iteration cannot improve quality through feedback.

**Key Implementation Notes**:

```python
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.tools import FunctionTool

# Exit tool for Critic to signal quality pass
def exit_loop(tool_context: ToolContext):
    """Signal that the output meets quality standards."""
    tool_context.actions.escalate = True
    tool_context.actions.skip_summarization = True
    return {}

# Generator sub-agent
page_generator = LlmAgent(
    name="PageGenerator",
    model=os.environ.get("PAGE_GENERATOR_MODEL", "gemini-2.0-flash"),
    instruction="""Generate documentation for the given source files.
    If previous feedback exists in the conversation, incorporate it.""",
    output_key="current_page_draft",  # Stores output in session state
)

# Critic sub-agent (can use different model)
page_critic = LlmAgent(
    name="PageCritic",
    model=os.environ.get("PAGE_CRITIC_MODEL", "gemini-2.0-flash"),
    instruction="""Evaluate the documentation draft against the rubric.
    If quality meets all criteria, call exit_loop.
    Otherwise, provide specific feedback for improvement.""",
    tools=[FunctionTool(exit_loop)],
)

# LoopAgent orchestrates the iteration
page_generation_loop = LoopAgent(
    name="PageGenerationLoop",
    sub_agents=[page_generator, page_critic],
    max_iterations=3,  # Configurable via env var
)
```

- **Feedback mechanism**: The Critic's response is automatically appended to session conversation history. On the next loop iteration, the Generator sees the full conversation including the Critic's feedback, enabling informed revision without explicit state plumbing.
- **output_key**: The Generator writes its draft to session state via `output_key`. The Critic reads this to evaluate. This is a clean data handoff within the loop.
- **Termination**: Two paths — (1) Critic calls `exit_loop` tool setting `escalate=True`, which exits the LoopAgent immediately, or (2) `max_iterations` is reached, at which point the best attempt (tracked by score in session state) is used.
- **CriticInput includes source_context**: Pass source files to the Critic via session state so it can verify code reference accuracy, not just prose quality.
- **Per-criterion minimum scores**: The Critic rubric includes per-criterion floors (e.g., `PAGE_ACCURACY_CRITERION_FLOOR >= 5.0`). Even if the overall score passes, a single criterion below its floor triggers another iteration.
- **Critic failure resilience**: If the Critic LLM call fails (timeout, rate limit), auto-pass the attempt with a warning logged. This prevents pipeline crashes from Critic infrastructure issues.
- **AgentResult wrapper**: After the loop completes, wrap results in `AgentResult[T]` carrying `evaluation_history`, `attempts`, `scores`, and `token_usage`.

**Sources**:
- [ADK Loop Agents Documentation](https://google.github.io/adk-docs/agents/workflow-agents/loop-agents/)
- [Developer's Guide to Multi-Agent Patterns in ADK](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/)
- [Build AI Agents That Self-Correct (ADK LoopAgent)](https://medium.com/google-developer-experts/build-ai-agents-that-self-correct-until-its-right-adk-loopagent-f620bf351462)
- [Multi-Agent Systems in ADK](https://google.github.io/adk-docs/agents/multi-agents/)

---

## 3. Prefect 3 Work Pool Patterns

**Decision**: Use two work pools — `local-dev` (process type) for development and `k8s-pool` (kubernetes type) for production. Select via `PREFECT_WORK_POOL` application-level environment variable. Use `AUTODOC_FLOW_DEPLOYMENT_PREFIX` (dev/prod) to target the correct deployment.

**Rationale**: Prefect 3 work pools define the infrastructure type for flow execution. By maintaining separate pools per environment, deployments can be promoted from dev to prod by changing the work pool reference. The process type runs flows locally (ideal for development and testing), while kubernetes type provisions K8s Jobs per flow run (production scalability). This is a standard Prefect pattern: "by switching a deployment's work pool, users can quickly change the worker that will execute their runs."

**Alternatives Considered**:
- **Single work pool with work queues** — Work queues within a single pool can provide priority and concurrency control, but don't change the underlying infrastructure type. Dev would still run in K8s, adding unnecessary complexity.
- **flow.serve() for dev** — Prefect's `serve()` runs flows locally without workers but doesn't use work pools at all, making it incompatible with the deployment model needed for production.
- **run_deployment for all environments** — Would require K8s infrastructure even in dev, increasing local setup complexity.

**Key Implementation Notes**:

```python
# config.py — work pool selection
import os

WORK_POOL = os.environ.get("PREFECT_WORK_POOL", "local-dev")
DEPLOYMENT_PREFIX = os.environ.get("AUTODOC_FLOW_DEPLOYMENT_PREFIX", "dev")

def get_deployment_name(flow_name: str) -> str:
    return f"{DEPLOYMENT_PREFIX}-{flow_name}"
```

```yaml
# prefect.yaml — dual deployment configuration
deployments:
  - name: dev-full-generation
    entrypoint: src/flows/full_generation.py:full_generation_flow
    work_pool:
      name: local-dev
    parameters:
      environment: dev

  - name: prod-full-generation
    entrypoint: src/flows/full_generation.py:full_generation_flow
    work_pool:
      name: k8s-pool
    parameters:
      environment: prod
```

- **Work pool creation**: Create pools via CLI or Terraform:
  ```bash
  prefect work-pool create local-dev --type process
  prefect work-pool create k8s-pool --type kubernetes
  ```
- **Worker startup**: In dev, run `prefect worker start --pool local-dev`. In prod, deploy the Prefect worker container with `--pool k8s-pool`.
- **Kubernetes job template**: The `k8s-pool` work pool's base job template specifies the Flow Runner Docker image, resource limits, environment variables, and service account. Customize via Prefect UI or `prefect work-pool update`.
- **Environment variable injection**: Both `PREFECT_WORK_POOL` and `AUTODOC_FLOW_DEPLOYMENT_PREFIX` are set in the respective environment's Docker Compose or K8s ConfigMap.
- **Three Docker images**: API (lightweight FastAPI), Worker (official Prefect image, lightweight), Flow Runner (heavy — AI libs, ADK, flow code baked in). The worker pulls the Flow Runner image for K8s Jobs.
- **CI builds flow image**: On merge to main, CI builds the Flow Runner image tagged with commit SHA (`APP_COMMIT_SHA` injected via `--build-arg`).

**Sources**:
- [Prefect 3 Work Pools Documentation](https://docs.prefect.io/v3/concepts/work-pools)
- [Configure Dynamic Infrastructure with Work Pools](https://docs.prefect.io/3.0/deploy/infrastructure-concepts/work-pools)
- [Prefect Kubernetes Worker](https://prefecthq.github.io/prefect-kubernetes/worker/)
- [Getting to Your First Flow Run: Prefect Worker & Deployment Setup](https://thescalableway.com/blog/getting-to-your-first-flow-run-prefect-worker-and-deployment-setup/)

---

## 4. Prefect 3 Concurrency Limits

**Decision**: Use tag-based concurrency limits to control parallel task execution. Define tags like `page-generation` and `llm-call` on tasks, and create corresponding concurrency limits at application startup using the Prefect Python client.

**Rationale**: Prefect 3's tag-based concurrency limits are the native mechanism for controlling parallel task execution. They are backed by global concurrency limits (as of Prefect 3.4.19) and are enforced server-side, meaning they work across multiple workers and flow runs. This prevents LLM rate-limit exhaustion and controls resource usage. Tasks exceeding the limit are held in a waiting state until a slot opens.

**Alternatives Considered**:
- **Global concurrency limits (direct)** — Lower-level mechanism. Tag-based limits are syntactic sugar over global limits (creating `tag:{tag_name}` entries). Using tags is more ergonomic and integrates directly with task decorators.
- **Asyncio semaphores in application code** — Only works within a single process. Doesn't coordinate across multiple workers or flow runs. Breaks the single-pod model if scaling later.
- **Rate limiting at reverse proxy** — Already planned for HTTP API rate limiting, but doesn't apply to internal task orchestration.

**Key Implementation Notes**:

```python
# startup.py — create concurrency limits on application startup
from prefect import get_client

async def ensure_concurrency_limits():
    """Create or update concurrency limits. Idempotent."""
    limits = {
        "page-generation": int(os.environ.get("PAGE_GENERATION_CONCURRENCY", "5")),
        "llm-call": int(os.environ.get("LLM_CALL_CONCURRENCY", "10")),
        "structure-extraction": int(os.environ.get("STRUCTURE_EXTRACTION_CONCURRENCY", "3")),
    }
    async with get_client() as client:
        for tag, limit in limits.items():
            await client.create_concurrency_limit(
                tag=tag,
                concurrency_limit=limit,
            )
```

```python
# tasks.py — tag tasks for concurrency control
from prefect import task

@task(tags=["page-generation", "llm-call"])
async def generate_page(page_spec: PageSpec) -> PageResult:
    """Generate a single documentation page."""
    ...
```

- **Multi-tag behavior**: If a task has multiple tags (e.g., `["page-generation", "llm-call"]`), it runs only if ALL tags have available concurrency slots. This provides layered control.
- **Zero limit = abort**: Setting a tag's concurrency limit to 0 causes immediate abortion of any task runs with that tag (useful for emergency throttling).
- **Wait behavior**: Delayed tasks wait and retry at intervals configurable via `PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS` (default: likely 30s).
- **CLI management**: `prefect concurrency-limit create page-generation 5`, `prefect concurrency-limit ls`, `prefect concurrency-limit inspect page-generation`.
- **Startup timing**: Call `ensure_concurrency_limits()` during FastAPI `lifespan` startup or as the first step in the worker's initialization, before any flows run.
- **Idempotency**: `create_concurrency_limit` is idempotent — calling it with the same tag updates the limit rather than failing.

**Sources**:
- [Prefect 3 Tag-Based Concurrency Limits](https://docs.prefect.io/v3/how-to-guides/workflows/tag-based-concurrency-limits)
- [Limit Concurrent Task Runs with Tags](https://docs-3.prefect.io/3.0/develop/task-run-limits)
- [Run Tasks Concurrently or in Parallel](https://docs.prefect.io/3.0/develop/task-runners)
- [Apply Global Concurrency and Rate Limits](https://docs-3.prefect.io/3.0/develop/global-concurrency-limits)

---

## 5. Prefect 3 Subflow Execution Model

**Decision**: Use direct subflow calls (not `run_deployment`) for scope processing. Nested `@flow` subflows run in-process in the parent pod by default. This preserves the single-pod execution model where parent and child flows share the same process, memory, and container.

**Rationale**: Prefect 3's default behavior for nested flows is in-process execution. When a flow function calls another `@flow`-decorated function, it creates a child flow run that executes in the same process. This is lightweight, avoids infrastructure provisioning latency, and maintains the single-pod model required by the architecture. Each scope's sub-flow (structure extraction, page generation, readme distillation) runs within the parent job's pod.

**Alternatives Considered**:
- **run_deployment()** — Triggers a new flow run via a deployment, which can run on different infrastructure (separate K8s Job). Adds latency for infrastructure provisioning, makes error handling harder (parent must poll for completion), and breaks the single-pod model. Use only when flows need different resources or images.
- **asyncio.gather for parallel scopes** — Compatible with in-process subflows. Use `asyncio.gather(*[process_scope(s) for s in scopes])` to run scope sub-flows concurrently within the same pod. This is the recommended pattern for parallel scope processing.
- **Prefect task runner (Dask/Ray)** — Overkill for scope-level parallelism. Task runners are for parallelizing individual tasks, not entire sub-flows.

**Key Implementation Notes**:

```python
from prefect import flow, task
import asyncio

@flow
async def process_scope(scope: Scope, repo_path: str) -> ScopeResult:
    """Sub-flow for processing a single documentation scope."""
    structure = await extract_structure(scope, repo_path)
    pages = await generate_pages(structure, repo_path)
    readme = await distill_readme(pages, scope)
    return ScopeResult(structure=structure, pages=pages, readme=readme)

@flow
async def full_generation_flow(repository_id: str, job_id: str):
    """Parent flow that fans out to scope sub-flows."""
    repo_path, commit_sha = await clone_repository(repository_id)
    scopes = await discover_scopes(repo_path)

    # Parallel scope processing — all run in-process
    scope_results = await asyncio.gather(
        *[process_scope(scope, repo_path) for scope in scopes]
    )

    await create_pr(scope_results, repository_id)
```

- **In-process confirmation**: Calling `process_scope(scope, repo_path)` directly (without `run_deployment`) guarantees in-process execution. The child flow run appears as a nested run in the Prefect UI, linked to the parent.
- **Task runner per subflow**: Each nested flow creates its own task runner for its tasks. When the subflow completes, its task runner shuts down. The parent flow's task runner is unaffected.
- **Blocking by default**: Synchronous subflow calls block the parent. Use `asyncio.gather` for concurrent execution of async subflows.
- **Error propagation**: Exceptions in subflows propagate to the parent flow naturally (same process). No need for polling or status checking.
- **Data passing**: Nested flow runs resolve task futures into data automatically, making it easy to pass results from tasks in the parent to the subflow.
- **Observability**: Each subflow gets its own flow run in the Prefect UI, with its own tasks, logs, and duration tracking. Parent-child relationships are visible.

**Sources**:
- [Prefect 3 Flows Documentation](https://docs.prefect.io/v3/concepts/flows)
- [Write and Run Flows](https://docs.prefect.io/3.0/develop/write-flows)
- [Subflow Options in Prefect 3](https://linen.prefect.io/t/29650833/ulva73b9p-what-options-i-have-to-run-subflow-from-main-flow)
- [run_deployment vs Direct Call](https://linen.prefect.io/t/29862670/ulva73b9p-can-i-execute-a-flow-run-from-another-deployed-flo)

---

## 6. pgvector HNSW Index with 3072 Dimensions

**Decision**: Use the `halfvec(3072)` type with an HNSW index using `halfvec_cosine_ops` for cosine distance. Build parameters: `m=24`, `ef_construction=128`. Query-time `hnsw.ef_search=100`.

**Rationale**: pgvector's standard `vector` type supports HNSW indexing only up to 2000 dimensions. For 3072-dimensional vectors (OpenAI text-embedding-3-large), the `halfvec` type must be used, which stores vectors in half-precision (16-bit float) and supports indexing up to 4000 dimensions. Half-precision reduces storage by 50% with minimal recall impact for search workloads. HNSW is preferred over IVFFlat for better query performance and no need to rebuild indexes after data changes.

**Alternatives Considered**:
- **IVFFlat index** — Lower build cost but requires periodic reindexing as data grows. Query performance is worse than HNSW, especially for high-dimensional data. The `probes` parameter requires careful tuning.
- **Dimensionality reduction (PCA to <2000)** — Would allow using the full `vector` type, but loses information and adds a preprocessing step. Not worth the complexity for the marginal storage savings.
- **Full-precision vector(3072) without index** — Exact nearest neighbor search. Accurate but O(n) scan time. Unusable beyond ~10K rows.
- **External vector database (Pinecone, Weaviate)** — Adds infrastructure complexity. pgvector keeps everything in PostgreSQL with ACID guarantees and transactional consistency with document metadata.

**Key Implementation Notes**:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table definition with halfvec for 3072 dimensions
CREATE TABLE wiki_page_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding halfvec(3072) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for cosine similarity with halfvec
CREATE INDEX idx_embeddings_hnsw ON wiki_page_embeddings
USING hnsw (embedding halfvec_cosine_ops)
WITH (m = 24, ef_construction = 128);

-- Full-text search support
ALTER TABLE wiki_pages ADD COLUMN fts tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX idx_pages_fts ON wiki_pages USING GIN (fts);
```

- **halfvec operator classes**: Use `halfvec_cosine_ops` (cosine distance), `halfvec_l2_ops` (Euclidean), or `halfvec_ip_ops` (inner product). Cosine is standard for text embeddings.
- **Build parameters**:
  - `m=24` (default 16): Higher than default because high-dimensional data benefits from more connections per node. Range 2-100; 24 balances recall and index size.
  - `ef_construction=128` (default 64): Higher value improves recall at the cost of slower index builds. One-time cost; worth it for better search quality.
- **Query-time tuning**:
  ```sql
  SET hnsw.ef_search = 100;  -- default is 40, max 1000
  ```
  Higher `ef_search` increases recall with sublinear speed decrease. Set per-session or per-transaction with `SET LOCAL`.
- **Storage impact**: `halfvec(3072)` = ~6KB per vector (vs ~12KB for full `vector(3072)`). For 10K pages with 5 chunks each = ~300MB index.
- **Index build time**: HNSW index builds are CPU-intensive. For 50K vectors at 3072 dimensions, expect 5-15 minutes. Build during off-peak or use `CREATE INDEX CONCURRENTLY`.
- **maintenance_work_mem**: Increase to at least 1GB for HNSW index builds: `SET maintenance_work_mem = '1GB';`

**Sources**:
- [pgvector GitHub — halfvec and HNSW](https://github.com/pgvector/pgvector)
- [HNSW Indexes with Postgres and pgvector (Crunchy Data)](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector)
- [Understanding Vector Search and HNSW with pgvector (Neon)](https://neon.com/blog/understanding-vector-search-and-hnsw-index-with-pgvector)
- [Optimize pgvector Search (Neon Docs)](https://neon.com/docs/ai/ai-vector-search-optimization)
- [AWS: Optimize with pgvector HNSW](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/)
- [Azure: Optimize pgvector Performance](https://learn.microsoft.com/en-us/azure/cosmos-db/postgresql/howto-optimize-performance-pgvector)

---

## 7. Reciprocal Rank Fusion (RRF) Implementation

**Decision**: Implement RRF as a PostgreSQL function combining full-text search (tsvector with `ts_rank_cd`) and semantic search (pgvector cosine distance) using two CTEs. Use `k=60` as the smoothing constant. Absent results from either list receive penalty rank 1000.

**Rationale**: RRF is scale-independent — it only cares about relative rankings, not raw scores. This eliminates the need to normalize scores between full-text search (arbitrary range) and cosine similarity (0-1 range). The k=60 value is the empirical standard from the original RRF paper. Implementing as a PostgreSQL function keeps everything server-side with ACID guarantees and avoids round-trips between application and database.

**Alternatives Considered**:
- **Score normalization + weighted average** — Requires normalizing disparate score ranges, which is fragile and sensitive to score distributions. Min-max normalization breaks when score ranges shift with data changes.
- **ParadeDB pg_search** — Provides BM25 ranking (better than ts_rank) and built-in hybrid search. Adds a PostgreSQL extension dependency. Worth evaluating for v2 if ts_rank proves insufficient.
- **Application-level fusion** — Run two separate queries, merge in Python. Adds latency (two round-trips) and loses transactional consistency.
- **Re-ranking with cross-encoder** — Higher quality but adds LLM inference cost per search. Disproportionate for a documentation search use case.

**Key Implementation Notes**:

```sql
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding halfvec(3072),
    match_count INTEGER DEFAULT 10,
    rrf_k INTEGER DEFAULT 60,
    full_text_weight FLOAT DEFAULT 1.0,
    semantic_weight FLOAT DEFAULT 1.0
)
RETURNS TABLE (
    page_id UUID,
    chunk_text TEXT,
    rrf_score FLOAT
)
LANGUAGE sql STABLE
AS $$
WITH semantic_search AS (
    SELECT
        e.page_id,
        e.chunk_text,
        ROW_NUMBER() OVER (
            ORDER BY e.embedding <=> query_embedding
        ) AS rank
    FROM wiki_page_embeddings e
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count * 2  -- Fetch 2x to ensure coverage after fusion
),
fulltext_search AS (
    SELECT
        p.id AS page_id,
        p.content AS chunk_text,
        ROW_NUMBER() OVER (
            ORDER BY ts_rank_cd(p.fts, websearch_to_tsquery('english', query_text)) DESC
        ) AS rank
    FROM wiki_pages p
    WHERE p.fts @@ websearch_to_tsquery('english', query_text)
    ORDER BY ts_rank_cd(p.fts, websearch_to_tsquery('english', query_text)) DESC
    LIMIT match_count * 2
),
combined AS (
    SELECT
        COALESCE(s.page_id, f.page_id) AS page_id,
        COALESCE(s.chunk_text, f.chunk_text) AS chunk_text,
        COALESCE(semantic_weight / (rrf_k + s.rank), 0.0) +
        COALESCE(full_text_weight / (rrf_k + f.rank), 0.0) AS rrf_score
    FROM semantic_search s
    FULL OUTER JOIN fulltext_search f
        ON s.page_id = f.page_id
)
SELECT page_id, chunk_text, rrf_score
FROM combined
ORDER BY rrf_score DESC
LIMIT match_count;
$$;
```

- **RRF formula**: `score = sum(weight / (k + rank))` per result across both lists. Higher k values flatten the score distribution (less emphasis on top ranks).
- **k=60**: Standard value from the original paper. Empirically robust across diverse retrieval scenarios. No strong reason to deviate.
- **Penalty rank 1000**: For results appearing in only one list, the absent list contributes `weight / (60 + 1000) ≈ 0.00094` — effectively zero but not exactly zero, maintaining the item's presence in results.
- **FULL OUTER JOIN**: Ensures results from either search type are included, even if they appear in only one. `COALESCE` handles NULL ranks from the absent list.
- **Weights**: `full_text_weight` and `semantic_weight` default to 1.0 (equal weighting). Adjustable per query — e.g., boost semantic for conceptual queries, boost full-text for exact API name lookups.
- **Performance**: Both CTEs use indexes (HNSW for semantic, GIN for full-text). The FULL OUTER JOIN operates on small result sets (match_count * 2 per CTE). Total query time should be under 100ms for typical workloads.
- **websearch_to_tsquery**: Parses natural language queries into tsquery format. More user-friendly than `plainto_tsquery` (supports AND/OR/NOT syntax).

**Sources**:
- [Hybrid Search in PostgreSQL: The Missing Manual (ParadeDB)](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [Hybrid Search with PostgreSQL and pgvector (Jonathan Katz)](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)
- [Supabase Hybrid Search Documentation](https://supabase.com/docs/guides/ai/hybrid-search)
- [Better RAG Results with RRF and Hybrid Search (Assembled)](https://www.assembled.com/blog/better-rag-results-with-reciprocal-rank-fusion-and-hybrid-search)
- [What is Reciprocal Rank Fusion? (ParadeDB)](https://www.paradedb.com/learn/search-concepts/reciprocal-rank-fusion)

---

## 8. OpenTelemetry TracerProvider + LoggingInstrumentor

**Decision**: Configure `TracerProvider` with `OTLPSpanExporter` at application entry point BEFORE any ADK imports. Use `LoggingInstrumentor` to inject `otelTraceID` and `otelSpanID` into structured JSON logs. Do NOT use `InProcessSpanExporter` — rely on AgentResult for agent-level metrics.

**Rationale**: ADK has built-in OpenTelemetry tracing that auto-instruments agent runs, LLM calls, and tool invocations. It requires a TracerProvider to be configured globally before ADK modules are imported. LoggingInstrumentor bridges tracing and logging by injecting trace context into every log record, enabling trace-log correlation without custom code. This approach provides full observability with minimal instrumentation code.

**Alternatives Considered**:
- **InProcessSpanExporter** — Stores spans in memory for programmatic access. Dropped in v2.2 because AgentResult carries token_usage and evaluation metrics directly. In-process storage adds memory overhead without justification.
- **Custom log filter for trace injection** — Manual implementation of what LoggingInstrumentor provides out-of-box. More code to maintain, higher risk of bugs.
- **Jaeger exporter** — Jaeger-specific. OTLP is the standard protocol supported by all backends (Jaeger, Grafana Tempo, Datadog, etc.). More portable.
- **No tracing (logs only)** — Loses the ability to correlate operations across agent calls, LLM requests, and database queries. Critical for debugging multi-agent flows.

**Key Implementation Notes**:

```python
# telemetry.py — MUST be imported before any ADK imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.logging import LoggingInstrumentor

def configure_telemetry():
    """Configure OpenTelemetry. Call before any ADK imports."""
    resource = Resource.create({
        "service.name": "autodoc-adk",
        "service.version": os.environ.get("APP_COMMIT_SHA", "dev"),
    })

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
            )
        )
    )
    trace.set_tracer_provider(tracer_provider)

    # Inject trace_id and span_id into all log records
    LoggingInstrumentor().instrument(set_logging_format=False)
    # set_logging_format=False: we use custom JSON formatter, not default format
```

```python
# logging_config.py — structured JSON logging with trace context
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "otelTraceID", "0" * 32),
            "span_id": getattr(record, "otelSpanID", "0" * 16),
            "service": getattr(record, "otelServiceName", "autodoc-adk"),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)
```

```python
# main.py — entry point ordering
from telemetry import configure_telemetry
configure_telemetry()  # MUST be first

# Now safe to import ADK
from google.adk.agents import LlmAgent
from google.adk.sessions import DatabaseSessionService
```

- **Import ordering is critical**: `configure_telemetry()` must execute before any `google.adk` imports. ADK checks for a global TracerProvider at import time. If none is set, it may configure its own (or skip tracing).
- **LoggingInstrumentor fields**: Injects `otelTraceID`, `otelSpanID`, `otelServiceName`, `otelTraceSampled` into every `logging.LogRecord`. Available via `getattr(record, "otelTraceID", default)`.
- **set_logging_format=False**: We use a custom JSON formatter, not the default text format. Setting to `True` would override the root logger's format string.
- **BatchSpanProcessor**: Batches spans for efficient export. Use `SimpleSpanProcessor` only in development (exports immediately but blocks).
- **ADK built-in spans**: ADK automatically creates spans for `agent.run`, `llm.generate`, `tool.execute`, etc. These appear in the trace without any custom instrumentation.
- **Packages required**:
  ```
  opentelemetry-api
  opentelemetry-sdk
  opentelemetry-exporter-otlp-proto-grpc
  opentelemetry-instrumentation-logging
  ```

**Sources**:
- [OpenTelemetry Logging Instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/logging/logging.html)
- [How to Inject Trace IDs into Application Logs with OTel SDKs](https://oneuptime.com/blog/post/2026-02-06-inject-trace-ids-application-logs-opentelemetry/view)
- [Google Cloud: Instrument ADK Applications with OpenTelemetry](https://docs.google.com/stackdriver/docs/instrumentation/ai-agent-adk)
- [Google ADK Observability with OpenTelemetry (SigNoz)](https://signoz.io/docs/google-adk-observability/)
- [opentelemetry-instrumentation-logging (PyPI)](https://pypi.org/project/opentelemetry-instrumentation-logging/)

---

## 9. SQLAlchemy Async + asyncpg Connection Pooling

**Decision**: Use `create_async_engine` with asyncpg driver and `AsyncAdaptedQueuePool`. Configure `pool_size=10`, `max_overflow=5`, `pool_timeout=30`, `pool_recycle=1800` via environment variables. Manage sessions within Prefect task boundaries using `async_sessionmaker` with explicit `async with` blocks.

**Rationale**: SQLAlchemy's `create_async_engine` automatically uses `AsyncAdaptedQueuePool`, an asyncio-compatible adaptation of `QueuePool`. asyncpg is the fastest async PostgreSQL driver for Python. The pool parameters are tuned for a documentation generator workload: moderate concurrency (parallel page generation), long-running transactions (LLM calls within tasks), and single-pod execution (no cross-pod pool sharing needed).

**Alternatives Considered**:
- **asyncpg pool directly (no SQLAlchemy)** — Lower-level, requires manual connection management and query building. Loses SQLAlchemy ORM, migrations (Alembic), and query composition. Not worth the micro-optimization.
- **psycopg3 async** — Viable alternative to asyncpg. asyncpg is more mature for async workloads and has better benchmarks for high-throughput scenarios.
- **NullPool (no pooling)** — Creates a new connection per operation. Excessive overhead for parallel page generation where many tasks run concurrently.
- **SQLModel** — Built on SQLAlchemy, adds Pydantic integration. Useful for FastAPI models but adds a dependency layer; direct SQLAlchemy is more transparent.

**Key Implementation Notes**:

```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import os

def create_engine():
    return create_async_engine(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://autodoc:password@localhost:5432/autodoc"
        ),
        pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "5")),
        pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "30")),
        pool_recycle=int(os.environ.get("DB_POOL_RECYCLE", "1800")),
        pool_pre_ping=True,  # Verify connections before checkout
        echo=os.environ.get("DB_ECHO", "false").lower() == "true",
    )

engine = create_engine()
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

```python
# Usage within Prefect tasks
from prefect import task

@task
async def save_page(page: WikiPage):
    async with async_session() as session:
        async with session.begin():
            session.add(page)
        # Commit happens automatically at end of begin() block
        # Session is returned to pool at end of async with
```

- **Pool sizing rationale**:
  - `pool_size=10`: Matches the expected concurrent task count for a single flow run. With 5 parallel page generation tasks + structure extraction + readme + embeddings + metadata operations, 10 covers peak demand.
  - `max_overflow=5`: Allows bursts up to 15 total connections (10 + 5). Overflow connections are discarded after use, not kept in pool.
  - `pool_timeout=30`: 30 seconds wait for a connection before raising `TimeoutError`. Generous enough for LLM-call-heavy tasks that hold connections.
  - `pool_recycle=1800`: Recycle connections after 30 minutes to prevent stale connections from PostgreSQL's `idle_in_transaction_session_timeout` or cloud proxy timeouts.
- **pool_pre_ping=True**: Sends a lightweight query (`SELECT 1`) before each checkout to verify the connection is alive. Adds ~1ms latency but prevents `ConnectionResetError` from stale connections.
- **expire_on_commit=False**: Prevents SQLAlchemy from expiring loaded attributes after commit. Important for Prefect tasks where you may return ORM objects from tasks and access their attributes in the flow.
- **Transaction scope = Prefect task**: Each `@task` function opens its own session and commits at the end. If the task fails, the transaction rolls back. Cross-task consistency is handled by Prefect flow retry.
- **AsyncAdaptedQueuePool**: Automatically used by `create_async_engine`. Do NOT specify `poolclass=QueuePool` — it's not asyncio-compatible. The async adaptation uses `asyncio.Queue` internally.
- **Event loop safety**: Do not share `AsyncEngine` across different event loops. In the single-pod model with Prefect, this is not an issue (one event loop per worker process).

**Sources**:
- [SQLAlchemy 2.0 Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [SQLAlchemy 2.0 Async I/O](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [How to Properly Set pool_size and max_overflow for ASGI Apps](https://www.pythontutorials.net/blog/how-to-properly-set-pool-size-and-max-overflow-in-sqlalchemy-for-asgi-app/)
- [Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, and asyncpg](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg)

---

## 10. AutoDoc MCP Server with FastMCP

**Decision**: Build the AutoDoc MCP server as a single Python file using `fastmcp` library, exposing exactly two tools (`find_repository` and `query_documents`). The server is a standalone process that connects to the application database for queries.

**Rationale**: FastMCP provides a minimal, decorator-based API for building MCP servers. With only two deterministic tools (database queries, no LLM involvement), the high-level FastMCP API eliminates boilerplate. The `@mcp.tool()` decorator handles schema generation, argument validation, and response formatting automatically. No ADK integration is needed on the server side — these are pure database query tools.

**Alternatives Considered**:
- **Low-level `mcp` Server class** — More control but significantly more boilerplate (manual tool listing, argument routing, error wrapping). Not justified for two simple tools.
- **ADK Agent as MCP server** — Expose an entire ADK agent via MCP. Overkill for two tools that are essentially database queries. Adds LLM overhead for deterministic operations.
- **ADK `adk_to_mcp_tool_type` conversion** — Converts ADK FunctionTools to MCP schema. Adds unnecessary ADK dependency to the MCP server. FastMCP generates schemas directly from Python type hints.

**Key Implementation Notes**:

```python
# src/mcp_server.py — single file, complete MCP server
from fastmcp import FastMCP

mcp = FastMCP("autodoc")

@mcp.tool()
async def find_repository(
    search: str,
) -> dict:
    """Find registered repositories by name, URL, or partial match.

    Args:
        search: Repository name, URL, or partial match string.

    Returns:
        Matching repositories with IDs, names, providers, and documented branches.
    """
    # DB lookup via RepositoryRepo
    ...

@mcp.tool()
async def query_documents(
    repo_url: str,
    query: str,
    search_type: str = "hybrid",
    limit: int = 10,
) -> dict:
    """Search documentation for a repository.

    Args:
        repo_url: Repository URL (resolved to repository_id internally).
        query: Natural language search query.
        search_type: One of 'semantic', 'text', or 'hybrid'.
        limit: Maximum results to return.

    Returns:
        Matching documentation pages ranked by relevance.
    """
    # Resolve repo_url → repository_id, then delegate to SearchRepo
    ...
```

- **Single file**: The entire MCP server lives in `src/mcp_server.py`. No ADK dependency required — it imports only `fastmcp` and the database access layer.
- **Schema from type hints**: FastMCP generates MCP tool schemas directly from Python function signatures and docstrings. No manual schema definition needed.
- **repo_url to repository_id translation**: `query_documents` accepts `repo_url` (user-friendly), internally resolves to `repository_id` via DB lookup. Auto-registers if the repository is not found (as specified in the architecture).
- **Transport**: FastMCP supports both stdio (for local MCP clients like Claude Code) and Streamable HTTP (for network clients). Default is stdio; configure HTTP for production deployment alongside the API.
- **Database access**: The MCP server imports and reuses the same `database/engine.py` and `database/repos/` classes as the API, ensuring consistent data access patterns.
- **Package required**: `fastmcp`

**Sources**:
- [FastMCP Documentation](https://gofastmcp.com/)
- [FastMCP GitHub](https://github.com/jlowin/fastmcp)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

---

## 11. Agent File Access via Filesystem MCP

**Decision**: ADK agents (StructureExtractor, PageGenerator) access cloned repository files through a filesystem MCP server, connected via ADK's `McpToolset`. The MCP server is scoped to the cloned repository directory. No git MCP server is needed — repositories are cloned by Prefect tasks using subprocess git commands, and diff detection uses the provider's compare API.

**Rationale**: ADK agents need to autonomously browse and read source files to generate documentation. Rather than pre-loading all file contents into the prompt (which hits context window limits for large repositories), the filesystem MCP server gives agents tool-based access to read files on demand. This is the idiomatic ADK pattern for giving agents access to external data. The filesystem MCP server is a standard, well-maintained MCP server that provides `read_file`, `list_directory`, `read_multiple_files`, and other file operations.

**Alternatives Considered**:
- **Pre-load all files into prompt context** — Simple but breaks for large repositories. A repo with 500 files would exceed any context window. The agent has no agency over which files to read.
- **Custom ADK FunctionTools for file access** — Write Python functions wrapped in `FunctionTool`. Works but reinvents what the filesystem MCP server already provides. More code to maintain, less standard.
- **Git MCP server** — Provides git-specific operations (log, diff, blame). Not needed because: (a) repos are cloned by Prefect tasks using subprocess git, (b) diff detection uses the provider's compare API (not git diff), (c) agents only need to read files, not interact with git history.
- **Direct file reading in agent prompts** — Read files in the Prefect task and inject content into agent session state. Loses the agent's ability to explore the codebase iteratively (e.g., follow imports, check related files).

**Key Implementation Notes**:

```python
# src/agents/common/mcp_tools.py
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, SseServerParams, StdioServerParams

async def create_filesystem_toolset(repo_path: str) -> McpToolset:
    """Create a filesystem MCP toolset scoped to the cloned repo directory.

    Args:
        repo_path: Absolute path to the cloned repository.

    Returns:
        McpToolset connected to the filesystem MCP server.
    """
    tools, exit_stack = await McpToolset.from_server(
        connection_params=StdioServerParams(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", repo_path],
        )
    )
    return tools, exit_stack
```

```python
# Usage in agent setup (e.g., StructureExtractor)
from google.adk.agents import LlmAgent, LoopAgent

async def build_structure_extractor(repo_path: str):
    fs_tools, exit_stack = await create_filesystem_toolset(repo_path)

    generator = LlmAgent(
        name="StructureGenerator",
        model=get_model(os.getenv("STRUCTURE_GENERATOR_MODEL")),
        instruction="Analyze the repository structure...",
        tools=fs_tools,  # Filesystem MCP tools
    )

    critic = LlmAgent(
        name="StructureCritic",
        model=get_model(os.getenv("STRUCTURE_CRITIC_MODEL")),
        instruction="Evaluate the documentation structure...",
        # Critic does NOT get filesystem tools — evaluates output only
    )

    loop = LoopAgent(
        name="StructureExtractionLoop",
        sub_agents=[generator, critic],
        max_iterations=3,
    )
    return loop, exit_stack
```

- **Scoped access**: The filesystem MCP server is started with the cloned repo path as its root. Agents cannot access files outside the repository directory. This provides sandboxed access.
- **Lifecycle**: The `exit_stack` must be cleaned up when the agent is done (closes the MCP server subprocess). Managed via `async with` in the Prefect task.
- **Which agents get filesystem tools**:
  - **StructureExtractor**: YES — needs to browse directory structure and read files to understand code organization.
  - **PageGenerator**: YES — needs to read source files referenced in the page spec to generate accurate documentation.
  - **ReadmeDistiller**: NO — works from generated wiki pages (passed via session state). Does not need direct file access.
- **Critic agents do NOT get filesystem tools**: Critics evaluate the generated output quality against the rubric. They receive source context via session state for accuracy verification, but don't autonomously browse the repo.
- **MCP server dependency**: The `@modelcontextprotocol/server-filesystem` package runs via `npx`. The Flow Runner Docker image must include Node.js for this. Alternatively, use a Python-based filesystem MCP server to avoid the Node.js dependency.
- **Connection type**: Uses `StdioServerParams` (subprocess communication). The MCP server runs as a child process of the Prefect task, automatically cleaned up when the task completes.

**Sources**:
- [ADK MCP Tools Documentation](https://google.github.io/adk-docs/tools/mcp-tools/)
- [MCP Filesystem Server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)
- [ADK McpToolset API](https://google.github.io/adk-docs/tools/mcp-tools/)

---

## 12. Page Chunking for Vector Embeddings

**Decision**: Separate vector embeddings from `wiki_pages` into a new `page_chunks` table (1:N). Use two-stage Markdown heading-aware chunking with recursive fallback for oversized sections. Default chunk size: 512 tokens, 50 token overlap, 50 token minimum. Search uses best-chunk-wins aggregation for RRF merge.

**Rationale**: Wiki pages can exceed the 8,191-token limit of `text-embedding-3-large`, causing truncation or failure. A single embedding per page represents the average semantic meaning across all topics, reducing retrieval precision. Chunk-level embeddings tightly represent specific sections, yielding more precise cosine similarity scores and more relevant search results.

**Alternatives Considered**:
- **Fixed-size token chunking** — Simple but splits mid-sentence, mid-code-block, loses document structure. Unsuitable for Markdown documentation.
- **Pure semantic chunking (embed every sentence, cluster)** — Expensive (requires embedding every sentence during chunking), unpredictable sizes. Overkill for already-structured content.
- **Sliding window with overlap** — Creates many redundant chunks, poor for structured content with clear heading boundaries.
- **Single embedding per page (current approach)** — Works only for short pages. Breaks for long documentation pages and reduces search precision.

**Key Implementation Notes**:

Stage 1: Split by Markdown headings (`#`, `##`, `###`), preserving heading hierarchy as metadata. Never split inside fenced code blocks or tables.

Stage 2: Sub-split oversized sections (> 512 tokens) using recursive character text splitting with separators `["\n\n", "\n", ". ", " "]`.

```python
# Chunk metadata per chunk:
{
    "wiki_page_id": UUID,          # FK to source page
    "chunk_index": int,            # 0-based position within page
    "heading_path": list[str],     # e.g., ["Authentication", "JWT Validation"]
    "heading_level": int,          # 0=preamble, 1-6 for heading levels
    "token_count": int,            # Actual token count (cl100k_base encoding)
    "start_char": int,             # Character offset in original page content
    "end_char": int,               # End character offset
    "has_code": bool,              # Contains fenced code block
}
```

Database schema — new `page_chunks` table:
```sql
CREATE TABLE page_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wiki_page_id UUID NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_embedding vector(3072) NOT NULL,
    heading_path TEXT[] NOT NULL DEFAULT '{}',
    heading_level INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    has_code BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE page_chunks ADD CONSTRAINT uq_page_chunk_index UNIQUE (wiki_page_id, chunk_index);
CREATE INDEX ix_page_chunks_embedding ON page_chunks USING hnsw (content_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 256);
CREATE INDEX ix_page_chunks_page_id ON page_chunks (wiki_page_id);
```

Search flow: semantic search on chunks → aggregate to page level (best-chunk-wins via PARTITION BY wiki_page_id) → RRF merge with page-level full-text → return pages with best matching chunk excerpts.

Configuration env vars: `CHUNK_MAX_TOKENS=512`, `CHUNK_OVERLAP_TOKENS=50`, `CHUNK_MIN_TOKENS=50`, `EMBEDDING_BATCH_SIZE=100`.

**Sources**:
- [Best Chunking Strategies for RAG in 2025 — Firecrawl](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025)
- [Chunking Strategies for LLM Applications — Pinecone](https://www.pinecone.io/learn/chunking-strategies/)
- [Finding the Best Chunking Strategy — NVIDIA](https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/)
- [How to Split Markdown by Headers — LangChain](https://python.langchain.com/docs/how_to/markdown_header_metadata_splitter/)

---

## 13. Prefect Server Database Management

**Decision**: Prefect Server auto-manages its own database schema via Alembic. Our `init-db.sql` only creates the `prefect` database and the pgvector extension on our `autodoc` database. No Prefect table definitions or pg_trgm creation in our scripts.

**Rationale**: Prefect Server runs Alembic migrations automatically on startup when `PREFECT_API_DATABASE_MIGRATE_ON_START=True` (the default). This includes creating all tables, indexes, and extensions (including `pg_trgm`). Attempting to manage Prefect's schema externally creates maintenance burden and version coupling.

**Alternatives Considered**:
- **Pre-create Prefect tables in init-db.sql** — Fragile; schema changes with each Prefect version. Alembic migrations handle versioning automatically.
- **Disable auto-migration, run manually** — Appropriate for production (set `PREFECT_API_DATABASE_MIGRATE_ON_START=false`, run `prefect server database upgrade -y` as init container). Not needed for dev/initial setup.

**Key Implementation Notes**:

Startup sequence:
1. PostgreSQL container starts, creates `autodoc` DB (via `POSTGRES_DB`), runs `init-db.sql` (creates `prefect` DB + pgvector extension)
2. Prefect server container starts, connects to `prefect` database
3. Auto-migration runs `alembic_upgrade("head")` — all Prefect tables, indexes, and `pg_trgm` extension created
4. Prefect server ready

`init-db.sql` content:
```sql
-- Creates the Prefect database on the shared PostgreSQL instance.
-- The 'autodoc' database is created automatically via POSTGRES_DB env var.
-- Prefect Server handles its own schema migrations.
CREATE DATABASE prefect;

-- pgvector extension for our application database (not Prefect's)
\c autodoc
CREATE EXTENSION IF NOT EXISTS vector;
```

Docker Compose pattern (health check required):
```yaml
postgres:
  image: pgvector/pgvector:pg16
  environment:
    POSTGRES_USER: autodoc
    POSTGRES_PASSWORD: autodoc
    POSTGRES_DB: autodoc
  volumes:
    - ./deployment/scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U autodoc"]
    interval: 5s
    timeout: 5s
    retries: 5

prefect-server:
  image: prefecthq/prefect:3-latest
  command: prefect server start --host 0.0.0.0
  depends_on:
    postgres:
      condition: service_healthy
  environment:
    PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://autodoc:autodoc@postgres:5432/prefect"
```

Prefect CLI database commands:
- `prefect server database upgrade` — Apply pending migrations
- `prefect server database downgrade` — Roll back
- `prefect server database reset` — Drop and recreate all tables

**Sources**:
- [Prefect Server Docker Compose Guide](https://docs.prefect.io/v3/how-to-guides/self-hosted/docker-compose)
- [Prefect Server Database CLI](https://docs.prefect.io/v3/api-ref/cli/server)
- [Prefect Server Database Utilities API](https://docs.prefect.io/v3/api-ref/python/prefect-server-utilities-database)

---

## 14. Kubernetes Job Per Scope (run_deployment Pattern)

**Decision**: Use Prefect 3's `run_deployment()` to dispatch each scope's processing as a separate Kubernetes job. Orchestrator flows (documentation_flow, incremental_flow) fan out via `run_deployment()`. Scope worker flows run in separate K8s pods via the `k8s-pool` work pool. Tasks within a scope flow run in-process in the same pod.

**Rationale**: Each scope's processing (structure extraction → page generation → readme → embeddings) is resource-intensive. Running each as a separate K8s job provides: (a) isolation — one scope's failure doesn't crash others, (b) independent resource scaling — heavy scopes can use more CPU/memory, (c) fault tolerance — failed scopes can be retried independently, (d) observability — each scope appears as a distinct flow run in Prefect UI.

**Alternatives Considered**:
- **In-process subflows (current design)** — Simpler but no isolation between scopes. All scopes share the same pod's memory and CPU. One scope's OOM or crash kills all scopes.
- **DaskTaskRunner for parallel tasks** — Distributes tasks to a Dask cluster. Adds complexity (Dask scheduler), not needed when Prefect's work pool already provides K8s job scheduling.
- **Each page as a separate K8s job** — Maximum isolation but extreme overhead. A repo with 50 pages per scope would spawn 50+ K8s jobs per scope.

**Key Implementation Notes**:

Architecture:
```
Prefect Server → K8s Worker (long-lived pod)
                      |
                      ├→ K8s Job: orchestrator_flow (lightweight)
                      │     ├→ clone_repo task (in-process)
                      │     ├→ discover_scopes task (in-process)
                      │     └→ run_deployment × N scopes → wait
                      │
                      ├→ K8s Job: scope_flow (scope A, heavy)
                      │     ├→ extract_structure task
                      │     ├→ generate_pages tasks (ThreadPoolTaskRunner)
                      │     ├→ distill_readme task
                      │     └→ generate_embeddings task
                      │
                      └→ K8s Job: scope_flow (scope B, heavy)
                            └→ ... same tasks ...
```

Orchestrator flow pattern:
```python
import asyncio
from prefect import flow
from prefect.deployments import run_deployment

@flow
async def documentation_flow(repository_id: str, job_id: str, branch: str):
    repo_path, commit_sha = await clone_repository(repository_id)
    scopes = await discover_autodoc_configs(repo_path)

    # Fan out: each scope gets its own K8s Job
    child_runs = await asyncio.gather(
        *[
            run_deployment(
                name="scope-flow/k8s",
                parameters={
                    "repository_id": repository_id,
                    "job_id": job_id,
                    "branch": branch,
                    "scope_path": scope.path,
                    "commit_sha": commit_sha,
                },
                timeout=None,  # Wait for completion
                idempotency_key=f"job-{job_id}-scope-{scope.path}",
            )
            for scope in scopes
        ]
    )

    # Post-scope: create PR, archive sessions, cleanup
    await create_pull_request(repository_id, branch, child_runs)
    await archive_adk_sessions(job_id)
    await cleanup_repository(repo_path)
```

Deployment registration:
```python
# Register deployments for all environments
scope_flow.deploy(name="k8s", work_pool_name="k8s-pool", image="autodoc-flow:latest")
scope_flow.deploy(name="dev", work_pool_name="local-dev")
documentation_flow.deploy(name="k8s", work_pool_name="orchestrator-pool", image="autodoc-flow:latest")
documentation_flow.deploy(name="dev", work_pool_name="local-dev")
```

Local dev: `local-dev` process pool — `run_deployment()` spawns local processes instead of K8s jobs. Same code path, lighter weight.

Deadlock prevention: Orchestrator flows run in `orchestrator-pool` (limit: 10), scope worker flows run in `k8s-pool` (limit: 50). Pools are independent — no contention.

**Sources**:
- [Prefect run_deployment API](https://docs.prefect.io/v3/api-ref/python/prefect-deployments-flow_runs)
- [Prefect Kubernetes Work Pools](https://docs.prefect.io/v3/how-to-guides/deployment_infra/kubernetes)
- [Prefect Deploy Flows with Python](https://docs.prefect.io/v3/how-to-guides/deployments/deploy-via-python)

---

## 15. Work Pool Concurrency Limits

**Decision**: Use Prefect 3 work pool concurrency limits to control the number of concurrent K8s jobs. Two production work pools: `orchestrator-pool` (limit: 10) for parent flows, `k8s-pool` (limit: 50) for scope worker flows. Replace the previous tag-based task concurrency approach.

**Rationale**: The requirement is to limit total concurrent K8s jobs in the cluster, not individual task concurrency within a pod. Work pool concurrency limits are the correct mechanism — they gate how many flow runs (K8s Jobs) the worker creates. Tag-based limits were designed for intra-pod task concurrency, which is a different concern.

**Alternatives Considered**:
- **Tag-based concurrency limits (previous design)** — Controls task-level concurrency within flows. Does not limit the number of K8s jobs. A tag limit of 5 on `page-generation` means at most 5 page-generation tasks run concurrently across all flows, but doesn't prevent 100 K8s jobs from being created.
- **Kubernetes ResourceQuotas** — Limits resources at the K8s namespace level. If a job exceeds the quota, the pod stays Pending. Prefect would see it as Running (the Job exists). Less graceful than Prefect-level gating.
- **Global concurrency limits** — Cross-cutting limits usable in code for any resource. More granular than work pool limits but require explicit code instrumentation.

**Key Implementation Notes**:

Setup:
```bash
# Create work pools
prefect work-pool create --type kubernetes orchestrator-pool
prefect work-pool create --type kubernetes k8s-pool
prefect work-pool create --type process local-dev

# Set concurrency limits
prefect work-pool set-concurrency-limit orchestrator-pool 10
prefect work-pool set-concurrency-limit k8s-pool 50
```

How it works: If the k8s-pool concurrency limit is 50 and 48 runs are currently Running or Pending, the worker only picks up 2 more runs from the queue. Additional runs remain in Scheduled state.

Deadlock prevention: Separate pools ensure orchestrator flows (which hold a slot while waiting for children via `run_deployment()`) never compete with worker flows for slots.

Work queue priorities within a pool (optional):
```
orchestrator-pool:
  critical (priority 1, limit 1) — emergency jobs
  default  (priority 10, no sub-limit)

k8s-pool:
  high    (priority 5, limit 10) — high-importance scopes
  default (priority 10, no sub-limit)
```

Env vars for configuration:
- `PREFECT_ORCHESTRATOR_POOL` (default: `orchestrator-pool`)
- `PREFECT_WORKER_POOL` (default: `k8s-pool`)
- `PREFECT_DEV_POOL` (default: `local-dev`)
- `ORCHESTRATOR_POOL_CONCURRENCY` (default: `10`)
- `WORKER_POOL_CONCURRENCY` (default: `50`)

**Sources**:
- [Prefect Work Pools](https://docs.prefect.io/v3/deploy/infrastructure-concepts/work-pools)
- [Prefect Global Concurrency Limits](https://docs.prefect.io/v3/how-to-guides/workflows/global-concurrency-limits)
- [Prefect work-pool CLI](https://docs.prefect.io/v3/api-ref/cli/work-pool)

---

## 16. Multi-Provider LLM Support (Google Vertex AI, Azure OpenAI, AWS Bedrock)

**Decision**: Use ADK's built-in `LiteLlm` wrapper (`google.adk.models.lite_llm.LiteLlm`) as the multi-provider abstraction. A thin `get_model()` factory function in `src/config/models.py` resolves provider-prefixed model strings into configured `LiteLlm` instances (or returns raw strings for native Gemini models).

**Rationale**: ADK already delegates non-Gemini model access to LiteLLM via its `LiteLlm` class. This is the officially supported path — no custom abstraction or proxy needed. The model string prefix (`vertex_ai/`, `azure/`, `bedrock/`) determines the provider at the LiteLLM routing level.

**Alternatives considered**:
- **LiteLLM Proxy Server**: Separate proxy service between ADK and providers. Rejected — adds deployment complexity and an extra network hop. Useful for centralized key management in multi-tenant setups but overkill for a single-service deployment.
- **LiteLLM Router**: Client-side load balancing with fallback across providers. Rejected — does not integrate with ADK's `LlmAgent(model=...)` parameter (Router is a standalone completion client). Retry/fallback is better handled at Prefect task level.
- **Custom BaseLlm subclass**: Implement a custom `BaseLlm` subclass that wraps multiple providers. Rejected — reinvents what LiteLLM already does. Higher maintenance burden.
- **ADK LLMRegistry with custom provider**: Register custom `BaseLlm` subclasses per provider. Rejected — LiteLlm already handles all providers through a single class.

**How ADK model resolution works**:

1. `LlmAgent(model="gemini-2.5-flash")` — String form. ADK's `LLMRegistry` regex-matches to the native `Gemini` class. No LiteLLM involved.
2. `LlmAgent(model=LiteLlm(model="azure/gpt4o-deploy"))` — Instance form. Registry bypassed. LiteLlm routes to Azure OpenAI via the `azure/` prefix.
3. The `model` parameter on `LlmAgent` accepts `Union[str, BaseLlm]`. `LiteLlm` extends `BaseLlm`.

**Provider string formats and env vars**:

| Provider | Model String Format | Required Env Vars |
|----------|-------------------|-------------------|
| Google Vertex AI | `vertex_ai/gemini-2.5-pro` | `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, `GOOGLE_APPLICATION_CREDENTIALS` |
| Google Gemini (AI Studio) | `gemini-2.5-flash` (native, no prefix) | `GOOGLE_API_KEY` |
| Azure OpenAI | `azure/<deployment-name>` | `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION` |
| AWS Bedrock | `bedrock/<model-id>` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME` |

**Factory function design** (`src/config/models.py`):

```python
from google.adk.models.lite_llm import LiteLlm

def get_model(
    model_string: str | None = None,
    **kwargs,
) -> str | LiteLlm:
    """Create a model instance from a provider-prefixed model string.

    Args:
        model_string: e.g. "gemini-2.5-flash", "azure/gpt4o-deploy",
                      "bedrock/anthropic.claude-3-sonnet-v1:0".
                      If None, reads DEFAULT_MODEL env var.
        **kwargs: Provider-specific overrides (api_key, api_base, etc.)

    Returns:
        Raw string for native Gemini models, LiteLlm instance for others.
    """
    model_string = model_string or os.getenv("DEFAULT_MODEL", "gemini-2.5-flash")

    # Native Gemini — return string for ADK's built-in resolution
    if not "/" in model_string or model_string.startswith("gemini"):
        return model_string

    # LiteLLM provider — inject provider-specific env-based defaults
    provider = model_string.split("/")[0]
    provider_kwargs = _get_provider_defaults(provider)
    provider_kwargs.update(kwargs)  # per-call overrides win

    return LiteLlm(model=model_string, **provider_kwargs)
```

**Per-agent override pattern**: Each agent reads its model from an env var (e.g., `PAGE_GENERATOR_MODEL=azure/gpt4o-deploy`). The factory resolves the string:

```python
generator = LlmAgent(
    model=get_model(os.getenv("PAGE_GENERATOR_MODEL")),
    name="page_generator",
    instruction="...",
)
critic = LlmAgent(
    model=get_model(os.getenv("PAGE_CRITIC_MODEL")),
    name="page_critic",
    instruction="...",
)
```

**Dependencies**: `litellm` (already an ADK optional dependency via `google-adk[extensions]`), `boto3>=1.28.57` for Bedrock, `google-cloud-aiplatform` for Vertex AI.

**Sources**:
- [ADK Models — LiteLLM](https://google.github.io/adk-docs/agents/models/litellm/)
- [ADK Models — Vertex AI](https://google.github.io/adk-docs/agents/models/vertex/)
- [LiteLLM Azure OpenAI](https://docs.litellm.ai/docs/providers/azure/)
- [LiteLLM AWS Bedrock](https://docs.litellm.ai/docs/providers/bedrock)
- [LiteLLM Google ADK Tutorial](https://docs.litellm.ai/docs/tutorials/google_adk)
- [ADK LLMRegistry Source](https://github.com/google/adk-python/blob/main/src/google/adk/models/registry.py)
