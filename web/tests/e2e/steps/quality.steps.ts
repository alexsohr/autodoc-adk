import { Then } from './bdd';

// ─────────────────────────────────────────────────────────────────────────────
// PTS-2.6 — Placeholder steps (Quality tab)
//
// PTS-2.6 is tagged @todo @known-gap and skipped at runtime by support/hooks.ts.
// The `@known-gap` tag is documentary: docs/ui/00-index.md notes that quality
// score charts are client-side simulated, so the acceptance bullet "scores
// are real values from the API" is not currently satisfiable. Implementation
// is deferred until the score charts are sourced from real API data.
//
// playwright-bdd codegen requires every step in every scenario to have a
// definition, even when the scenario will be skipped — so each placeholder
// below resolves immediately. They will be replaced with real implementations
// in the per-scenario PR that removes the @todo tag.
// See features/README.md § Authoring a new feature.
//
// When implementing, point assertions at the QualityTab PO locators
// (agentCard('Structure Extractor'|'Page Generator'|'README Distiller'),
// pageQualityTable). Add testids as needed for scope filter buttons + page
// title links + table column headers.
// ─────────────────────────────────────────────────────────────────────────────

Then(
  'the Quality agent card for {string} is visible with score, trend, and run history',
  async ({}, _agent: string) => {
    // @todo: implement when PTS-2.6 is wired up — assert
    //        QualityTab.agentCard(agent) is visible and contains the score,
    //        a trend indicator, and the run history sparkline.
    await Promise.resolve();
  },
);

Then('the Quality tab scope filter buttons are visible', async () => {
  // @todo: implement when PTS-2.6 is wired up — needs a testid on the scope
  //        filter button group in QualityTab source + matching PO locator.
  await Promise.resolve();
});

Then(
  'the Quality tab Page Quality table shows columns {string}, {string}, {string}, {string}, {string}',
  async ({}, _c1: string, _c2: string, _c3: string, _c4: string, _c5: string) => {
    // @todo: implement when PTS-2.6 is wired up — assert each column header
    //        is present in QualityTab.pageQualityTable. Likely reuses the
    //        same `data-testid="datatable-header-${col.key}"` pattern that
    //        DataTable already emits, scoped to the Quality table.
    await Promise.resolve();
  },
);

Then(
  'the Quality tab Page Quality table page titles are clickable links to the Docs tab',
  async () => {
    // @todo: implement when PTS-2.6 is wired up — assert the first row's
    //        page title is an <a> with an href that lands on /docs/<slug>.
    await Promise.resolve();
  },
);

Then(
  'the Quality tab Page Quality scores are real values from the API',
  async () => {
    // @todo @known-gap: the source currently renders client-side simulated
    //        scores with fixed offsets (see 00-index.md observation). When
    //        the chart wiring is replaced by real API data, this step will
    //        compare visible scores against the GET /repos/{id}/quality API
    //        response.
    await Promise.resolve();
  },
);
