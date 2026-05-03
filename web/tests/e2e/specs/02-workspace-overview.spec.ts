import { test, expect } from '../fixtures/test';
import { WorkspacePage } from '../pages/WorkspacePage';
import { REPOS } from '../helpers/seed-data';

// Source: docs/ui/02-repo-workspace-overview.md
// Scenarios: docs/ui/test-scenarios/02-workspace-overview.test-scenarios.md

test.describe('02 — Repo Workspace Overview', () => {

  test('PTS-2.1: full workspace load with data', async ({ page }) => {
    const ws = new WorkspacePage(page);
    await ws.goto(REPOS.digitalClock.id);

    await expect(ws.breadcrumb).toContainText('Repositories');
    await expect(ws.breadcrumb).toContainText(REPOS.digitalClock.name);
    for (const card of ['Doc Pages', 'Avg Quality', 'Scopes', 'Last Generated'] as const) {
      await expect(ws.metricCard(card)).toBeVisible();
    }
    await expect(ws.runFullGenButton).toBeVisible();
    for (const tab of ['Overview', 'Docs', 'Search', 'Chat', 'Jobs', 'Quality', 'Settings'] as const) {
      await expect(ws.tab(tab)).toBeVisible();
    }
  });

  test.skip('PTS-2.2: tab navigation preserves repo context', async ({ page }) => {
    // Acceptance: each of 7 tabs sets [active] / aria-current and renders its
    // distinct content; breadcrumb, repo name, and Run Full Generation button
    // remain visible across all tabs.
  });
});
