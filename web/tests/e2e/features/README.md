# Gherkin Features

Features in this directory are the **executable behavioral spec** for the AutoDoc dashboard.

## Source-of-truth alignment (binding)

Every `Scenario:` MUST correspond to a PTS-N.M scenario in
`docs/ui/00-index.md` § Page-Level Test Results. The mapping is:

| .feature file                       | UI doc                                                | PTS scenarios     |
|-------------------------------------|-------------------------------------------------------|-------------------|
| 01-repo-list-and-nav.feature ✅     | docs/ui/01-repository-list-and-navigation.md          | PTS-1.1..1.6      |
| 02-workspace-overview.feature ✅    | docs/ui/02-repo-workspace-overview.md                 | PTS-2.1, 2.2      |
| 03-docs-search-chat.feature ✅      | docs/ui/03-repo-workspace-docs-search-chat.md         | PTS-2.3, 2.4      |
| 04-jobs-quality-settings.feature ✅ | docs/ui/04-repo-workspace-jobs-quality-settings.md    | PTS-2.5..2.7      |
| 05-admin-health-and-jobs.feature ✅ | docs/ui/05-admin-health-and-jobs.md                   | PTS-3.1, 3.2, 3.5 |
| 06-admin-usage-and-mcp.feature ✅   | docs/ui/06-admin-usage-and-mcp.md                     | PTS-3.3, 3.4      |

## Migration status

All six areas are migrated. The legacy `web/tests/e2e/specs/` directory
and the `fixtures/` re-export shim have been retired (PR 07, cleanup).
Of the 18 scenarios authored across the six features:

- **Implemented and runnable today** (6): PTS-1.1, PTS-2.1, PTS-2.4,
  PTS-2.5, PTS-3.1, PTS-3.3. These pass against the live UI under
  `--project=bdd-chromium` (and `bdd-firefox`).
- **`@todo` placeholders** (12): the remaining PTS scenarios in each
  area. The Gherkin steps fully encode the acceptance criteria — they
  are the executable spec waiting for wiring. A separate post-migration
  backlog (one PR per scenario) lifts the `@todo` tag.

## Conventions

- **Title**: `Scenario: PTS-N.M — <description from 00-index.md>` (PTS ID is part of the title for traceability).
- **Acceptance criteria**: each bullet from the matching PTS in 00-index.md MUST appear as a Then/And step.
- **Tags**:
  - `@smoke` — run on every CI lane.
  - `@todo` — auto-skipped by `support/hooks.ts`. Use for unimplemented scenarios. The auto-skip fires in a `Before` hook before any step body runs, so placeholder step definitions for `@todo` scenarios are never executed.
  - `@known-gap` — scenario covers a documented gap from 00-index.md § Known Gaps; cite the gap row inline as a Gherkin comment.
  - `@as-developer` / `@as-viewer` — opt the scenario into a role-specific `page` fixture. The override in `support/auth.ts` reads `$tags` and constructs a fresh `BrowserContext` with `X-Forwarded-Role: developer` (or `viewer`) for the duration of the scenario; absence of either tag preserves the admin default from `playwright.config.ts:use.extraHTTPHeaders`. Existing steps need no changes — they keep destructuring `page` and receive the role-aware page automatically. There is no `@as-admin` tag because admin is the implicit default.
  - `@area-<name>` — at the Feature level, groups scenarios by UI area for `--grep` filtering.
- **Selectors**: NEVER appear in step text or step definitions. Live in `web/tests/e2e/pages/*.ts` only. Steps call PO methods/locators.
- **Seed data**: parameterize as `{string}` in scenarios; resolve via `REPOS.<symbolicName>` from `support/seed-data.ts` in step definitions. Example: a scenario step `the "digitalClock" repository card is visible` resolves `digitalClock` to `REPOS.digitalClock` and asserts on `repos.card(REPOS.digitalClock.name)`.

### Placeholder steps for `@todo` scenarios

`playwright-bdd` is configured with `missingSteps: 'fail-on-gen'`, so codegen fails if any step in any scenario lacks a step definition — even when the scenario is going to be skipped at runtime by the `@todo` `Before` hook.

To keep codegen passing without weakening the safety net, every step that appears only in `@todo` scenarios has a one-line placeholder definition in the corresponding `steps/<area>.steps.ts`:

```ts
When('I do the thing', async () => {
  // @todo: implemented in per-area PR for PTS-N.M
  await Promise.resolve();
});
```

These placeholders never execute (the `@todo` `Before` hook calls `test.skip()` before any step body runs). They exist only to satisfy the codegen contract. They are removed and replaced with real implementations in the per-area PR that drops the `@todo` tag from the scenario.

## Authoring a new feature (per-area PR)

1. Pick the next `0N-*.feature` in the table above (or open an existing
   one to lift a `@todo` placeholder).
2. Read the UI doc and 00-index.md for that area's PTS scenarios.
3. Write Scenarios — title format above, steps mirror the acceptance criteria 1:1.
4. Add domain step definitions in `web/tests/e2e/steps/<area>.steps.ts`, reusing common steps where possible.
5. If a step is needed but cannot be implemented yet, leave the scenario `@todo` and provide a placeholder step body (`// @todo: …`).
6. PR description must include the alignment checklist from the plan: `/Users/alex/.claude/plans/i-have-a-problem-refactored-riddle.md` § Doc-alignment verification.
