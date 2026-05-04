import { test, expect } from '../fixtures/test';
import { UsagePage } from '../pages/admin/UsagePage';

// Source: docs/ui/06-admin-usage-and-mcp.md
// Scenarios: docs/ui/test-scenarios/06-admin-usage-and-mcp.test-scenarios.md

test.describe('06 — Admin · Usage / Costs & MCP Servers', () => {

  test('PTS-3.3: usage and costs page loads', async ({ asDeveloper }) => {
    const usage = new UsagePage(asDeveloper);
    await usage.goto();

    await expect(usage.heading).toBeVisible();
    for (const r of ['7 days', '30 days', '90 days', 'All time'] as const) {
      await expect(usage.rangeButton(r)).toBeVisible();
    }
    for (const card of ['Total Tokens', 'Estimated Cost', 'Total Jobs'] as const) {
      await expect(usage.metricCard(card)).toBeVisible();
    }

    // Regression guard for the AdminUsageResponse field-name mismatch:
    // a frontend that reads stale keys would render zero placeholders even
    // when the backend reports non-zero totals. The seed inserts exactly one
    // COMPLETED job with token_usage so these cards must contain a non-zero
    // digit (e.g. "2K", "$0.02", "1").
    const tokensCard = usage.metricCard('Total Tokens');
    const costCard = usage.metricCard('Estimated Cost');
    const jobsCard = usage.metricCard('Total Jobs');
    await expect(tokensCard).toContainText(/[1-9]/);
    await expect(costCard).toContainText(/\$[\d.]*[1-9]/);
    await expect(jobsCard).toContainText(/[1-9]/);
  });

  test.skip('PTS-3.4: mcp servers page loads', async ({ asDeveloper }) => {
    // Acceptance: heading, server status card with endpoint URL + copy button,
    // available tools list, summary metric cards, agent integration tabs (3),
    // security context panel.
  });
});
