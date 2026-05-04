import { test, expect } from '../fixtures/test';
import { WorkspacePage } from '../pages/WorkspacePage';
import { JobsTab } from '../pages/JobsTab';
import { REPOS } from '../helpers/seed-data';

// Source: docs/ui/04-repo-workspace-jobs-quality-settings.md
// Scenarios: docs/ui/test-scenarios/04-jobs-quality-settings.test-scenarios.md

test.describe('04 — Repo Workspace · Jobs / Quality / Settings', () => {

  test('PTS-2.5: jobs tab partitions render with seeded data', async ({ page }) => {
    const ws = new WorkspacePage(page);
    await ws.goto(REPOS.digitalClock.id);
    await ws.tab('Jobs').click();

    const jobs = new JobsTab(page);
    await expect(jobs.completedSection).toBeVisible();
    await expect(jobs.failedSection).toBeVisible();
    await expect(jobs.cancelledSection).toBeVisible();
    await expect(jobs.dryRunCheckbox).toBeVisible();
    await expect(jobs.fullGenButton).toBeVisible();
    await expect(jobs.incrementalButton).toBeVisible();

    // Seeded data: 1 completed, 13 failed, 6 cancelled.
    await expect(jobs.filterPill('Completed')).toContainText(/Completed\(1\)/);
    await expect(jobs.filterPill('Failed')).toContainText(/Failed\(13\)/);
    await expect(jobs.filterPill('Cancelled')).toContainText(/Cancelled\(6\)/);
  });

  test.skip('PTS-2.6: quality tab shows scores', async ({ page }) => {
    // Acceptance: 3 agent score cards; scope filter; page quality table sortable;
    // page titles link to docs; pagination footer reflects 10 pages.
  });

  test.skip('PTS-2.7: settings tab sub-navigation', async ({ page }) => {
    // Acceptance: 5 sub-tabs (General, Branches, Webhooks, AutoDoc Config, Danger Zone)
    // each set to [active] when clicked; render distinct content panels.
  });
});
