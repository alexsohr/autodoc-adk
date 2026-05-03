# Add E2E Playwright tests for feature {{NN}} — {{slug}}

## Why
The AutoDoc dashboard has a {{short_feature_description}}. UI behavior is documented
in `docs/ui/{{NN}}-{{ui_slug}}.md`. Test scenarios for this feature are defined in
`docs/ui/test-scenarios/{{NN}}-{{slug}}.test-scenarios.md`. The Playwright spec
scaffold at `web/tests/e2e/specs/{{NN}}-{{slug}}.spec.ts` has one worked-example
test and the remaining scenarios as `test.skip` placeholders.

## What changes
Implement every `test.skip` in `web/tests/e2e/specs/{{NN}}-{{slug}}.spec.ts` per
the assertions in `docs/ui/test-scenarios/{{NN}}-{{slug}}.test-scenarios.md`.

Constraints:
- Use the worked example in the same spec file as the implementation pattern.
- Reuse Page Objects in `web/tests/e2e/pages/`. Add methods/locators there when
  needed — never put selectors in spec files.
- Use fixtures from `web/tests/e2e/fixtures/test.ts`. Default `page` is admin;
  opt into `asViewer` / `asDeveloper` for role-gated assertions.
- Reference seeded fixtures via typed constants in `web/tests/e2e/helpers/seed-data.ts`.
- Tests that fail due to underlying app bugs stay red — do not dilute assertions
  to make them pass. Note known-bug failures in the change description.

## Spec deltas
- ADDED: capability `e2e/feature-{{NN}}` covering PTS-{{NN}}.1 … PTS-{{NN}}.{{M}}.

## Acceptance
- `cd web && AUTODOC_E2E=1 npx playwright test --config tests/e2e/playwright.config.ts specs/{{NN}}-*` runs all scenarios.
- 0 `test.skip` remain in the target spec file.
- Change description lists each PTS ID with pass/fail outcome from the local run.
