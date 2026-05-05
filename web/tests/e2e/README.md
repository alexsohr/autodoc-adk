# AutoDoc Dashboard — Playwright E2E Tests

## Run locally

```bash
# Terminal 1: backend (Postgres + API in stub mode)
cd deployment && make dev-up && make migrate
cd ..
AUTODOC_E2E=1 DEFAULT_MODEL=stub EMBEDDING_MODEL=stub \
  uv run uvicorn src.main:app --host 0.0.0.0 --port 8080

# Terminal 2: built web served by vite preview
cd web && npm run build && npx vite preview --port 5173

# Terminal 3: tests
cd web && npm run test:e2e          # headless
cd web && npm run test:e2e:ui       # Playwright UI
cd web && npm run test:e2e:headed   # headed Chromium
```

`globalSetup` polls `http://localhost:8080/health`, calls `POST /_e2e/reset`, runs
`uv run python -m tests.e2e_seed.seed_playwright`, and writes the manifest to
`web/tests/e2e/.seed-data.json` (gitignored).

## Folder layout

- `specs/` — six hand-written spec files (`01-…06-`), one per `docs/ui/0N-*.md` feature.
- `features/` — Gherkin `.feature` files (BDD scenarios). Compiled by playwright-bdd.
- `steps/` — Step definitions (`bdd.ts` wires `createBdd(authTest)`; `*.steps.ts` are domain steps).
- `pages/` — Page Objects. Both specs and steps use these; selectors do not appear in spec/step files.
- `support/` — `auth.ts` (role contexts), `api-stubs.ts` (route mocks), `seed-data.ts` (typed manifest re-export), `hooks.ts` (BDD Before/After), `world.ts` (scenario-scoped state shape), `selectors.ts`.
- `fixtures/test.ts` — legacy re-export kept so the existing `specs/0N-*.spec.ts` keep working; new tests should not import from here.

## Test scenarios

`docs/ui/test-scenarios/0N-*.test-scenarios.md` is the assertion-level spec for
each feature. Per-feature opsx changes implement skipped tests by reading those
files plus the corresponding `docs/ui/0N-*.md` UI description.

## CI lanes

| Workflow | Trigger | Browsers | Real LLM |
|---|---|---|---|
| `ci.yml` `playwright-pr` | PR + push to main | chromium | no (stub) |
| `playwright-nightly.yml` | cron 06:00 UTC + manual | chromium + firefox | no (stub) |
| `playwright-live.yml` | manual + `live-llm` PR label | chromium | yes (gated env) |

The BDD projects (`bdd-chromium`, `bdd-firefox`) are not yet wired into CI; run them locally via `--project=bdd-chromium` (or omit `--project` to run everything).

## Debugging

- Trace viewer: `npx playwright show-trace test-results/*/trace.zip`.
- HTML report: `npx playwright show-report` after a run.
- Add `--debug` to step through a single test in inspector mode.

## Adding a new test

For an existing feature (01–06): edit the relevant `specs/0N-*.spec.ts` and the
matching `docs/ui/test-scenarios/0N-*.test-scenarios.md`. Add Page Object methods
when needed. Do **not** put raw selectors in spec files.
