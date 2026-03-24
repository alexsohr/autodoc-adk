## Context

AutoDoc ADK has unit tests (~20+ files) and integration tests that mock repositories at the FastAPI dependency level. However, no tests exercise the full pipeline: HTTP request → Prefect flow execution → agent invocation → database persistence → search retrieval. This means wiring bugs between layers (e.g., a renamed field in AgentResult, a broken import in a flow task, or a migration that drops a column) go undetected until manual testing or production.

The existing test infrastructure provides patterns to build on:
- `asyncio_mode = "auto"` for async tests
- `httpx.AsyncClient` with `ASGITransport` for in-process API testing
- `app.dependency_overrides` for injecting test doubles
- Dev-mode flow submission via `asyncio.create_task()` (in-process, no Prefect worker needed)

## Goals / Non-Goals

**Goals:**
- Exercise the full pipeline (API → flow → agent → DB → search) with real PostgreSQL and real application code
- Achieve deterministic, zero-cost test runs by stubbing only at external boundaries (LLM, Git, embeddings)
- Run under 3 minutes in CI, gating every PR
- Catch schema drift between agent stubs and real agent output schemas via Pydantic validation
- Provide a fixture/stub framework that makes adding new E2E scenarios easy (<30 min per scenario)

**Non-Goals:**
- Testing LLM output quality (domain of golden-file tests, separate effort)
- Testing real Git clone operations against remote repositories
- Testing Prefect worker dispatch in Kubernetes mode (test only dev-mode in-process execution)
- Testing real embedding model inference
- Replacing existing unit or integration tests

## Decisions

### 1. Stub at `BaseAgent.run()`, not at flow task level

**Decision:** Patch `BaseAgent.run()` (or each agent subclass's `run()`) to return canned `AgentResult[T]` responses.

**Rationale:** Patching at the agent boundary keeps all flow task logic real — DB writes, quality report aggregation, error handling, token usage tracking. Patching at the flow task level would skip too much internal logic and reduce the test's ability to catch regressions.

**Alternative considered:** Patching at `run_quality_loop()` — rejected because it would skip the quality loop orchestration itself, which is a critical code path (criterion floors, max attempts, below_minimum_floor).

### 2. Real PostgreSQL via testcontainers-python, not SQLite or docker-compose

**Decision:** Use `testcontainers-python` (`testcontainers[postgres]`) to programmatically spin up a PostgreSQL 18 + pgvector container from a session-scoped pytest fixture. Run Alembic migrations once at session start.

**Rationale:** SQLite lacks pgvector support and has semantic differences with PostgreSQL (e.g., JSON operators, array types). testcontainers makes tests fully self-contained — no separate docker-compose file to manage, no manual container lifecycle. The container starts in ~2s and is reused across the test session. Cleanup is automatic via context manager.

**Alternative considered:** docker-compose.test.yml — rejected after framework evaluation. testcontainers is more portable (no docker-compose dependency), more standard in the testing world, and avoids managing a separate infra file. The Python dependency is minimal (already using Docker for dev).

### 3. Transaction-based test isolation with SAVEPOINT

**Decision:** Each test function runs inside a database transaction that rolls back via SAVEPOINT after the test completes.

**Rationale:** This is faster than truncating tables or recreating the schema between tests. It also ensures complete isolation — each test sees a clean database without needing explicit cleanup.

**Caveat:** Flow tasks that create their own sessions (via `get_session_factory()`) will need the engine/session factory to be overridden to use the test transaction. This requires patching `get_engine()` and `get_session_factory()` at the module level.

### 4. In-process flow execution (dev mode), not Prefect worker

**Decision:** Use Prefect's `prefect_test_harness()` context manager and ensure `AUTODOC_FLOW_DEPLOYMENT_PREFIX=dev` so flows run via `asyncio.create_task()` in-process.

**Rationale:** This makes tests synchronous from the caller's perspective (await the task), deterministic, and debuggable. No need for a Prefect server, worker, or work pool in the test environment.

**Alternative considered:** Running a real Prefect server in docker-compose.test.yml — rejected as it adds 10+ seconds of startup time, requires Redis, and introduces network-level flakiness without testing any code we own.

### 5. Deterministic hash-based embedding vectors

**Decision:** The embedding stub generates vectors by hashing input text, producing deterministic float vectors where similar text produces vectors with non-zero cosine similarity.

**Rationale:** Using random vectors would make search assertions non-deterministic. Using zero vectors would prevent testing vector search at all. Hash-based vectors are deterministic and produce meaningful (though imperfect) similarity relationships, enabling search correctness assertions.

**Implementation:** Use `hashlib.sha256(text.encode()).digest()` to seed a numpy random generator, then generate a 1024-dim unit vector. Same text always produces the same vector.

### 6. Frozen fixture repositories, not dynamically generated

**Decision:** Check in minimal fixture repos under `tests/e2e/fixtures/` — one for baseline (`sample-repo/`) and one with modifications (`sample-repo-v2/`).

**Rationale:** Frozen fixtures ensure reproducibility and make tests self-documenting. Dynamic generation would add complexity and risk test flakiness.

### 7. Override `get_db_session` and engine at dependency level

**Decision:** Override FastAPI's `get_db_session` dependency to yield the test transaction session. Additionally, patch `get_engine()` and `get_session_factory()` so flow tasks (which create sessions outside FastAPI's dependency injection) also use the test database.

**Rationale:** Flow tasks call `get_session_factory()` directly (not via FastAPI Depends), so dependency overrides alone are insufficient. Both pathways must be patched to ensure all DB operations hit the test database within the test transaction.

### 8. No Prefect server or Redis in test infrastructure

**Decision:** The testcontainers setup only spins up PostgreSQL + pgvector. No Prefect server, no Redis.

**Rationale:** With `prefect_test_harness()` and dev-mode flow submission, Prefect's server is not needed. This reduces container startup time and eliminates a source of flakiness.

### 9. Plain pytest over BDD frameworks (pytest-bdd, behave, etc.)

**Decision:** Use plain pytest + httpx.AsyncClient + testcontainers. No BDD framework.

**Rationale:** After evaluating pytest-bdd, behave, Robot Framework, tavern, and Schemathesis: every BDD framework in the Python ecosystem has a fundamental async incompatibility. pytest-bdd's async step support (PR #349) has been unmerged since 2022. behave is a standalone runner incompatible with pytest fixtures. The project is fully async (every agent, flow task, DB operation, API handler). Wrapping every step in `asyncio.run()` would be ugly and defeat `asyncio_mode="auto"`. Human-readable scenarios are not a priority — code readability is sufficient.

**Alternative considered:** pytest-bdd — rejected due to async incompatibility. Schemathesis — recommended as a complementary addition (OpenAPI fuzz testing) but not an E2E replacement; it cannot test multi-step flows or verify DB state.

### 10. Tiered scenario prioritization

**Decision:** Organize ~86 scenarios into three implementation tiers: Tier 1 (must-have, ~25 scenarios) covers core happy paths + error paths for the flows being tested manually today. Tier 2 (important, ~30 scenarios) covers webhooks, job lifecycle edges, incremental subtleties. Tier 3 (nice-to-have, ~31 scenarios) covers pagination, health checks, validation corners.

**Rationale:** Implementing all 86 scenarios at once is too large. Tiering lets us deliver value incrementally — Tier 1 alone replaces manual E2E testing. Tiers 2 and 3 harden the suite.

### 11. Webhook payload factories for provider testing

**Decision:** Add `make_github_push_payload()` and `make_bitbucket_push_payload()` factories to generate valid webhook payloads with configurable repo URL, branch, and commit SHA.

**Rationale:** Webhook handling is a significant untested surface area (7 scenarios). Payload factories make it easy to test all webhook code paths including provider detection, payload parsing, and silent-skip behavior.

## Risks / Trade-offs

**[Stub drift]** → Stubs return shapes that no longer match real agent output. **Mitigation:** All stubs construct real Pydantic model instances (`AgentResult[WikiStructureSpec]`, etc.). If schemas change, Pydantic validation fails at test time, surfacing the drift immediately.

**[Session/transaction isolation with flows]** → Flow tasks create their own DB sessions via `get_session_factory()`, bypassing the test transaction. **Mitigation:** Patch `get_engine()` to return the test engine and `get_session_factory()` to return a factory bound to the test connection. All sessions within a test share the same underlying connection and transaction.

**[In-process flow execution hides K8s-specific bugs]** → Tests won't catch issues with task serialization across process boundaries or K8s job dispatch. **Mitigation:** This is an accepted limitation. Task parameters are already JSON-serializable by design. K8s dispatch is infrastructure, not application logic.

**[Test DB startup time]** → PostgreSQL container takes 2-5s to start. **Mitigation:** Session-scoped testcontainers fixture starts the container once per test session. Migrations also run once.

**[Transaction rollback hides commit-related bugs]** → Tests don't exercise actual commits, so isolation-level bugs or constraint violations that only surface on commit are invisible. **Mitigation:** Critical constraint checks (unique, FK) are enforced immediately by PostgreSQL, not deferred to commit time. This is an accepted minor risk.

**[~86 scenarios is a large test suite]** → Risk of slow tests or maintenance burden. **Mitigation:** Tiered implementation — Tier 1 (~25 scenarios) delivers immediate value. Many scenarios share fixtures and stubs, so incremental cost per scenario is low after infrastructure is in place. Target remains under 3 minutes total.
