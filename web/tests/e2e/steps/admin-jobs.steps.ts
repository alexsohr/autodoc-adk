import { Then, When } from './bdd';

// ─────────────────────────────────────────────────────────────────────────────
// PTS-3.2 — All Jobs full page with filtering
//
// Scenario is tagged @todo + @known-gap and is auto-skipped at runtime by
// support/hooks.ts. Placeholder step bodies exist only to satisfy
// playwright-bdd's `missingSteps: 'fail-on-gen'` codegen contract.
//
// Two known gaps from docs/ui/00-index.md § Known Gaps are referenced inline
// in the .feature file:
//   - "All Jobs CANCELLED filter — Status tracked in counts but absent from
//     filter chips" (00-index.md:143)
//   - "All Jobs pagination — No cursor pagination, only first 20 jobs shown"
//     (00-index.md:142)
//
// These will be replaced with real implementations when the @todo tag is
// dropped, the AllJobsPage PO is extended (table column headers, row expand
// detail panel, pagination footer), and the underlying gaps are addressed.
// ─────────────────────────────────────────────────────────────────────────────

When('I open the All Jobs page', async () => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

Then('the All Jobs heading is visible', async () => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

Then('the All Jobs subtitle is visible', async () => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

Then('the All Jobs filter pill {string} shows a count', async ({}, _name: string) => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

When('I click the All Jobs filter pill {string}', async ({}, _name: string) => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

Then('the All Jobs filter pill {string} is marked active', async ({}, _name: string) => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

Then('the All Jobs table only shows rows with status {string}', async ({}, _status: string) => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

Then('the All Jobs table column header {string} is visible', async ({}, _header: string) => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

Then('the All Jobs search field is visible', async () => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

When('I click a non-link cell of the first All Jobs row', async () => {
  // @todo: implemented in per-area PR for PTS-3.2
  await Promise.resolve();
});

Then(
  'the All Jobs row detail panel shows Job ID, Commit, Mode, Updated, and Error message',
  async () => {
    // @todo: implemented in per-area PR for PTS-3.2
    await Promise.resolve();
  },
);

Then(
  'the All Jobs pagination footer shows {string} with Previous and Next buttons',
  async ({}, _format: string) => {
    // @todo: implemented in per-area PR for PTS-3.2
    // @known-gap: All Jobs pagination not implemented (00-index.md § Known Gaps,
    // line 142). Step text encodes the documented acceptance criterion; the
    // implementation will land alongside the pagination feature.
    await Promise.resolve();
  },
);
