import { expect } from '@playwright/test';
import { Given, Then, When } from './bdd';
import { WorkspacePage } from '../pages/WorkspacePage';
import { REPOS, type SeedRepo } from '../support/seed-data';

// ─────────────────────────────────────────────────────────────────────────────
// Seed lookup helper
//
// Mirrors the pattern in repo-list.steps.ts: scenarios reference repositories
// by symbolic seed name (e.g. "digitalClock"), not by their displayed `name`.
// We resolve the symbolic name to the seed record here so step text stays
// stable when displayed names or generated IDs change.
// ─────────────────────────────────────────────────────────────────────────────
type SeedKey = keyof typeof REPOS;

function resolveSeedRepo(symbolic: string): SeedRepo {
  if (!(symbolic in REPOS)) {
    throw new Error(
      `Unknown seed repo "${symbolic}". Known keys: ${Object.keys(REPOS).join(', ')}`,
    );
  }
  return REPOS[symbolic as SeedKey];
}

type TabName = 'Overview' | 'Docs' | 'Search' | 'Chat' | 'Jobs' | 'Quality' | 'Settings';
type MetricCardName = 'Doc Pages' | 'Avg Quality' | 'Scopes' | 'Last Generated';

// ─────────────────────────────────────────────────────────────────────────────
// PTS-2.1 — Implemented steps
// ─────────────────────────────────────────────────────────────────────────────

Given(
  'I open the {string} repository workspace',
  async ({ page }, symbolic: string) => {
    const seed = resolveSeedRepo(symbolic);
    const ws = new WorkspacePage(page);
    await ws.goto(seed.id);
  },
);

Then('the URL path matches the repository workspace pattern', async ({ page }) => {
  // /repos/{uuid} — accept any non-empty path segment after /repos/.
  await expect(page).toHaveURL(/\/repos\/[^/]+\/?$/);
});

Then(
  'the breadcrumb shows {string} and the {string} repository name',
  async ({ page }, prefix: string, symbolic: string) => {
    const seed = resolveSeedRepo(symbolic);
    const ws = new WorkspacePage(page);
    await expect(ws.breadcrumb).toContainText(prefix);
    await expect(ws.breadcrumb).toContainText(seed.name);
  },
);

Then(
  'the {string} overview metric card is visible',
  async ({ page }, name: string) => {
    const ws = new WorkspacePage(page);
    await expect(ws.metricCard(name as MetricCardName)).toBeVisible();
  },
);

Then('the {string} button is visible', async ({ page }, label: string) => {
  // Currently only used for the "Run Full Generation" workspace header CTA.
  // If a future scenario needs other named buttons, broaden the lookup
  // (e.g. via a switch on `label`) rather than overload this step.
  if (label !== 'Run Full Generation') {
    throw new Error(
      `Step "the {string} button is visible" only supports "Run Full Generation" today; got "${label}".`,
    );
  }
  const ws = new WorkspacePage(page);
  await expect(ws.runFullGenButton).toBeVisible();
});

Then('the Overview Current Job card is visible', async ({ page }) => {
  const ws = new WorkspacePage(page);
  await expect(ws.currentJobCard).toBeVisible();
});

Then('the Overview Repository Info panel is visible', async ({ page }) => {
  const ws = new WorkspacePage(page);
  await expect(ws.repoInfoPanel).toBeVisible();
});

Then('the Overview Recent Activity panel is visible', async ({ page }) => {
  const ws = new WorkspacePage(page);
  await expect(ws.recentActivityPanel).toBeVisible();
});

Then('the Overview Scope Breakdown table is visible', async ({ page }) => {
  const ws = new WorkspacePage(page);
  await expect(ws.scopeBreakdownTable).toBeVisible();
});

Then('the workspace {string} tab is visible', async ({ page }, name: string) => {
  const ws = new WorkspacePage(page);
  await expect(ws.tab(name as TabName)).toBeVisible();
});

// ─────────────────────────────────────────────────────────────────────────────
// PTS-2.2 — Placeholder steps
//
// PTS-2.2 is tagged @todo and skipped at runtime by support/hooks.ts.
// playwright-bdd codegen requires every step in every scenario to have a
// definition, even when the scenario will be skipped — so each placeholder
// below resolves immediately. They will be replaced with real implementations
// in the per-scenario PR that removes the @todo tag.
// See features/README.md § Authoring a new feature.
// ─────────────────────────────────────────────────────────────────────────────

When('I click the workspace {string} tab', async ({}, _name: string) => {
  // @todo: implement when PTS-2.2 is wired up
  await Promise.resolve();
});

Then(
  'the URL path corresponds to the {string} workspace tab',
  async ({}, _name: string) => {
    // @todo: implement when PTS-2.2 is wired up
    await Promise.resolve();
  },
);

Then(
  'the workspace {string} tab is marked active',
  async ({}, _name: string) => {
    // @todo: implement when PTS-2.2 is wired up
    await Promise.resolve();
  },
);

Then('the {string} tab content is rendered', async ({}, _name: string) => {
  // @todo: implement when PTS-2.2 is wired up
  await Promise.resolve();
});

Then(
  'the breadcrumb still shows the {string} repository name',
  async ({}, _symbolic: string) => {
    // @todo: implement when PTS-2.2 is wired up
    await Promise.resolve();
  },
);

Then('the {string} button is still visible', async ({}, _label: string) => {
  // @todo: implement when PTS-2.2 is wired up
  await Promise.resolve();
});

Then(
  'the workspace header still shows the {string} repository name and status',
  async ({}, _symbolic: string) => {
    // @todo: implement when PTS-2.2 is wired up — assert WorkspacePage.header shows
    //        REPOS[symbolic].name and a status badge (PO needs a `header` Locator).
    await Promise.resolve();
    void _symbolic;
  },
);
