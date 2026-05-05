import { Then, When } from './bdd';

// ─────────────────────────────────────────────────────────────────────────────
// PTS-3.5 — Cross-admin navigation
//
// Scenario is tagged @todo + @as-developer and is auto-skipped at runtime by
// support/hooks.ts. Placeholder step bodies exist only to satisfy
// playwright-bdd's `missingSteps: 'fail-on-gen'` codegen contract.
//
// Step phrasing here intentionally differs from the PTS-1.6 placeholders in
// repo-list.steps.ts ("I click the sidebar {string} link" vs. our "I click
// the {string} sidebar link") so playwright-bdd does not see them as
// duplicate definitions. When PTS-1.6 and PTS-3.5 are both implemented, the
// two phrasings can be unified into a single common.steps.ts step bound to
// the Sidebar PO.
//
// File kept separate from common.steps.ts for symmetry with the other admin
// step files (admin-health.steps.ts, admin-jobs.steps.ts); promote later if
// the navigation pattern generalizes.
// ─────────────────────────────────────────────────────────────────────────────

When('I click the {string} sidebar link', async ({}, _label: string) => {
  // @todo: implemented in per-area PR for PTS-3.5 — clicks Sidebar PO link
  // by label (System Health / All Jobs / Repositories).
  await Promise.resolve();
});

Then('the URL becomes {string}', async ({}, _url: string) => {
  // @todo: implemented in per-area PR for PTS-3.5
  await Promise.resolve();
});

Then('the {string} admin page heading is visible', async ({}, _heading: string) => {
  // @todo: implemented in per-area PR for PTS-3.5 — heading text from
  // 00-index.md § PTS-3.5 ("Infrastructure Snapshot" / "All Jobs" /
  // "Repositories").
  await Promise.resolve();
});

Then('the {string} sidebar link is highlighted as active', async ({}, _label: string) => {
  // @todo: implemented in per-area PR for PTS-3.5
  await Promise.resolve();
});

Then('the home page repository list is fully restored', async () => {
  // @todo: implemented in per-area PR for PTS-3.5 — covers acceptance bullet
  // "Navigating back to Repositories restores the home page".
  await Promise.resolve();
});

Then('the navigation transitions are instant client-side routes', async () => {
  // @todo: implemented in per-area PR for PTS-3.5 — covers acceptance bullet
  // "All transitions are instant (client-side routing)". Likely implemented
  // by asserting no page.on('load') fires between successive navigations
  // within the scenario.
  await Promise.resolve();
});
