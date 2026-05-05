# AutoDoc Dashboard — Playwright E2E Tests

The dashboard E2E suite is **Gherkin-only**. `playwright-bdd@^8.5.0`
compiles `features/*.feature` into Playwright test files at config-load
time. The legacy `specs/` directory and `fixtures/` re-export shim have
been retired — this README reflects the post-migration state.

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

`globalSetup` polls `http://localhost:8080/health`, calls `POST /_e2e/reset`,
runs `uv run python -m tests.e2e_seed.seed_playwright`, and writes the
manifest to `web/tests/e2e/.seed-data.json` (gitignored).

## Folder layout

- `features/` — Gherkin `.feature` files (BDD scenarios), authoring entry point.
- `steps/` — Step definitions. `bdd.ts` wires `createBdd(authTest)`;
  `*.steps.ts` are domain steps that delegate to Page Objects.
- `pages/` — Page Objects. Testid-based locators only; selectors do not
  appear in feature or step files.
- `support/` — `auth.ts` (role contexts), `api-stubs.ts` (route mocks),
  `seed-data.ts` (typed manifest re-export), `hooks.ts` (BDD Before/After,
  `@todo` skip), `console-errors.ts` (`trackConsoleErrors` /
  `expectNoConsoleErrors`).

## CI lanes

| Workflow | Trigger | Browsers | Real LLM |
|---|---|---|---|
| `ci.yml` `playwright-pr` | PR + push to main | chromium | no (stub) |
| `playwright-nightly.yml` | cron 06:00 UTC + manual | chromium + firefox | no (stub) |
| `playwright-live.yml` | manual + `live-llm` PR label | chromium | yes (gated env) |

The `chromium`/`firefox` projects are kept for CI workflow compatibility
but are now empty (the `specs/` directory they pointed at is gone, so
they list 0 tests). The `bdd-chromium`/`bdd-firefox` projects carry every
PTS scenario. CI workflows continue to invoke both project sets in one
Playwright run, so no workflow change is required.

## Debugging

- Trace viewer: `npx playwright show-trace test-results/*/trace.zip`.
- HTML report: `npx playwright show-report` after a run.
- Add `--debug` to step through a single scenario in inspector mode.

## Authoring a new scenario

See `web/tests/e2e/features/README.md` for the full per-area workflow,
binding alignment table, tag conventions, and `@todo` placeholder
pattern. The companion CLI prompt at `.claude/prompts/e2e-feature.prompt.md`
summarises the four-layer flow.
