## Why

Unit tests miss integration regressions in wiring, schema evolution, flow orchestration, and data persistence. There is no automated way to verify the full pipeline (API -> Prefect flow -> DB -> search) works end-to-end without calling real LLM providers. All E2E testing is currently done manually, which is slow, unrepeatable, and blocks rapid iteration. We need a deterministic, zero-cost E2E test suite covering every API-initiated scenario so tests can be repeated automatically after every change.

## What Changes

- Add a comprehensive E2E test suite (~86 scenarios) that exercises every API endpoint and flow path, organized into three tiers by priority
- Introduce canned agent stubs that replace all LLM calls with pre-built `AgentResult` responses, patching at the narrowest boundary (`BaseAgent.run()`) to maximize real code under test
- Use `testcontainers-python` for programmatic PostgreSQL 18 + pgvector container management (no separate docker-compose file needed)
- Create frozen fixture repositories (`sample-repo/`, `sample-repo-v2/`, `sample-monorepo/`) as deterministic test inputs
- Add deterministic embedding generation (hash-based vectors) enabling meaningful vector search assertions
- Add webhook stub factories for GitHub and Bitbucket push event payloads
- Add Makefile targets (`test-e2e`, `test-all`, `test-e2e-clean`) and CI pipeline stage for E2E tests

## Capabilities

### New Capabilities

- `e2e-test-infrastructure`: Test database via testcontainers-python (programmatic PostgreSQL + pgvector), Alembic migrations, SAVEPOINT transaction isolation, FastAPI test client wiring, and Prefect test harness for synchronous in-process flow execution
- `e2e-agent-stubs`: Canned agent response factories for StructureExtractor, PageGenerator, ReadmeDistiller, plus deterministic embedding, provider, webhook payload, and callback stubs — all type-annotated for schema drift detection
- `e2e-test-scenarios`: ~86 test scenarios across 8 groups (repository CRUD, job lifecycle, full generation flow, incremental update flow, error propagation, documents & search, webhooks, health check), organized into three implementation tiers

### Modified Capabilities

_None — this change introduces new test infrastructure without modifying existing capability requirements._

## Impact

- **New files**: `tests/e2e/` directory with conftest, stubs, fixtures, and 10 test modules; new Makefile targets
- **Dependencies**: `testcontainers[postgres]` (test DB), `httpx` (test client), `pytest-asyncio` (already present)
- **CI**: New pipeline stage running E2E tests in parallel with unit/integration tests
- **Existing code**: No modifications to application source code; stubs patch at runtime boundaries only
