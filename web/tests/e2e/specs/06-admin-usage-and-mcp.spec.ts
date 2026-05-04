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
  });

  test.skip('PTS-3.4: mcp servers page loads', async ({ asDeveloper }) => {
    // Acceptance: heading, server status card with endpoint URL + copy button,
    // available tools list, summary metric cards, agent integration tabs (3),
    // security context panel.
  });
});
