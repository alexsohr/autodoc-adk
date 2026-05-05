import { expect } from '@playwright/test';
import { Then } from './bdd';
import { JobsTab } from '../pages/JobsTab';
import { REPOS, type SeedRepo } from '../support/seed-data';

// ─────────────────────────────────────────────────────────────────────────────
// Seed lookup helper
//
// Mirrors the pattern in repo-list.steps.ts / workspace.steps.ts / docs.steps.ts:
// scenarios reference repositories by symbolic seed name. PTS-2.5 doesn't
// reference a repo directly in any Then step (the scenario opens the workspace
// via the Given step in workspace.steps.ts), so we keep the helper here as a
// silent re-export only — it lets future Jobs scenarios stay self-contained.
//
// The three local copies (here, in workspace.steps.ts, in docs.steps.ts) are
// intentional for this PR; lifting to a shared support module is a follow-up.
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

type FilterPillName = 'All' | 'Running' | 'Completed' | 'Failed' | 'Cancelled' | 'Pending';
type ColumnHeaderLabel = 'Status' | 'Mode' | 'Branch' | 'Created' | 'Updated' | 'PR';

// Maps the Gherkin-friendly column header text to the React column `key`,
// which is what `data-testid="datatable-header-${col.key}"` is built from.
// Mirrors `buildCompletedColumns()` in src/pages/tabs/JobsTab.tsx.
const COLUMN_KEY: Record<ColumnHeaderLabel, string> = {
  Status:  'status',
  Mode:    'mode',
  Branch:  'branch',
  Created: 'created_at',
  Updated: 'updated_at',
  PR:      'pull_request_url',
};

// ─────────────────────────────────────────────────────────────────────────────
// PTS-2.5 — Implemented steps (Jobs tab partitions + filter pills + columns)
// ─────────────────────────────────────────────────────────────────────────────

Then('the Jobs tab Completed section is visible', async ({ page }) => {
  const jobs = new JobsTab(page);
  await expect(jobs.completedSection).toBeVisible();
});

Then('the Jobs tab Failed section is visible', async ({ page }) => {
  const jobs = new JobsTab(page);
  await expect(jobs.failedSection).toBeVisible();
});

Then('the Jobs tab Cancelled section is visible', async ({ page }) => {
  const jobs = new JobsTab(page);
  await expect(jobs.cancelledSection).toBeVisible();
});

Then('the Jobs tab header shows the Dry Run checkbox', async ({ page }) => {
  const jobs = new JobsTab(page);
  await expect(jobs.dryRunCheckbox).toBeVisible();
});

Then('the Jobs tab header shows the Full Generation button', async ({ page }) => {
  const jobs = new JobsTab(page);
  await expect(jobs.fullGenButton).toBeVisible();
});

Then('the Jobs tab header shows the Incremental button', async ({ page }) => {
  const jobs = new JobsTab(page);
  await expect(jobs.incrementalButton).toBeVisible();
});

Then(
  'the Jobs tab filter pill {string} shows count {int}',
  async ({ page }, name: string, count: number) => {
    const jobs = new JobsTab(page);
    // FilterBar renders pills as `<Label>(<count>)`, e.g. `Failed(13)`. We
    // use a substring match (toContainText) to stay tolerant of whitespace
    // and the surrounding pill chrome. The leading word matters because the
    // FilterBar puts every pill in a single rendered string per pill button.
    await expect(jobs.filterPill(name as FilterPillName)).toContainText(
      `${name}(${count})`,
    );
  },
);

Then(
  'the Jobs tab Failed section column header {string} is visible',
  async ({ page }, header: string) => {
    const jobs = new JobsTab(page);
    const key = COLUMN_KEY[header as ColumnHeaderLabel];
    if (!key) {
      throw new Error(
        `Unknown Failed-section column header "${header}". Known: ${Object.keys(COLUMN_KEY).join(', ')}`,
      );
    }
    await expect(jobs.failedColumnHeader(key as Parameters<JobsTab['failedColumnHeader']>[0])).toBeVisible();
  },
);

Then(
  'the Jobs tab Failed section has a Retry button on at least one row',
  async ({ page }) => {
    const jobs = new JobsTab(page);
    await expect(jobs.firstFailedRetryButton).toBeVisible();
  },
);

Then(
  'the Jobs tab has a Details link on at least one row',
  async ({ page }) => {
    const jobs = new JobsTab(page);
    await expect(jobs.firstDetailsLink).toBeVisible();
  },
);

Then(
  'the Jobs tab Failed section pagination footer is visible',
  async ({ page }) => {
    const jobs = new JobsTab(page);
    // Seed fixture: 13 Failed jobs > pageSize=5 → paginator must render.
    await expect(jobs.failedSectionPagination).toBeVisible();
    await expect(jobs.failedSectionPagination).toContainText(/Showing 1.+5 of 13/);
  },
);

// resolveSeedRepo currently unused at runtime in this file — keep the import
// + helper colocated for symmetry with other steps files and to silence the
// unused-export lint noise without adding the helper to support/.
void resolveSeedRepo;
