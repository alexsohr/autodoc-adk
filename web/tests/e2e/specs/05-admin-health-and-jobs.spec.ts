import { test, expect } from '../fixtures/test';
import { HealthPage } from '../pages/admin/HealthPage';

// Source: docs/ui/05-admin-health-and-jobs.md
// Scenarios: docs/ui/test-scenarios/05-admin-health-and-jobs.test-scenarios.md

test.describe('05 — Admin · System Health & All Jobs', () => {

  test('PTS-3.1: system health page loads with all sections', async ({ asDeveloper }) => {
    const health = new HealthPage(asDeveloper);
    await health.goto();

    await expect(health.heading).toBeVisible();
    for (const card of ['API Cluster', 'Prefect Server', 'PostgreSQL', 'Active Workers'] as const) {
      await expect(health.serviceCard(card)).toBeVisible();
    }
    await expect(health.workPoolsTable).toBeVisible();
  });

  test.skip('PTS-3.2: all jobs filtering and row expand', async ({ asDeveloper }) => {
    // Acceptance: filter pills work; clicking a non-link row cell expands inline
    // detail panel showing Job ID, Commit, Mode, Updated, Error message.
  });
});
