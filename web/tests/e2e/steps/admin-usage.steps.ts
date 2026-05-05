import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { Then, When } from './bdd';
import { UsagePage } from '../pages/admin/UsagePage';

// ─────────────────────────────────────────────────────────────────────────────
// Console-error tracking
//
// PTS-3.3's acceptance criteria from docs/ui/00-index.md ends with "no console
// errors". Same pattern as steps/admin-health.steps.ts (PR 05): per-Page
// WeakMap of error messages, listener registered before navigation. The
// duplication is intentional for now; will be lifted into a shared support
// module in the cleanup PR (07).
//
// WeakMap (rather than a module-level Map) keyed on the Page lets entries
// disappear automatically when the BrowserContext closes — important because
// the @as-developer fixture builds a fresh context per scenario.
// ─────────────────────────────────────────────────────────────────────────────
const CONSOLE_ERRORS = new WeakMap<Page, string[]>();

async function gotoUsageWithConsoleTracking(page: Page): Promise<void> {
  const errors: string[] = [];
  CONSOLE_ERRORS.set(page, errors);
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });
  const usage = new UsagePage(page);
  await usage.goto();
}

type Range = '7 days' | '30 days' | '90 days' | 'All time';
type MetricCard = 'Total Tokens' | 'Estimated Cost' | 'Total Jobs';

// Subtitle text rendered below each metric card value (from MetricCard
// `subtitle` prop in src/pages/admin/UsageCostsPage.tsx). The card label
// itself ("Total Tokens" etc.) is also inside the testid container, so we
// match against the secondary-text fragment that is unique to each card.
const METRIC_CARD_SECONDARY_RE: Record<MetricCard, RegExp> = {
  'Total Tokens':   /Input:.*Output:/i,
  'Estimated Cost': /Based on input\/output token rates/i,
  'Total Jobs':     /Completed jobs in range/i,
};

function isRange(name: string): name is Range {
  return name === '7 days' || name === '30 days' || name === '90 days' || name === 'All time';
}

function isMetricCard(name: string): name is MetricCard {
  return name === 'Total Tokens' || name === 'Estimated Cost' || name === 'Total Jobs';
}

// ─────────────────────────────────────────────────────────────────────────────
// PTS-3.3 — Implemented steps (Usage & Costs full page)
// ─────────────────────────────────────────────────────────────────────────────

When('I open the Usage and Costs page', async ({ page }) => {
  await gotoUsageWithConsoleTracking(page);
});

Then('the Usage and Costs heading is visible', async ({ page }) => {
  const usage = new UsagePage(page);
  await expect(usage.heading).toBeVisible();
});

Then('the Usage and Costs subtitle is visible', async ({ page }) => {
  const usage = new UsagePage(page);
  await expect(usage.subtitle).toBeVisible();
});

Then(
  'the Usage and Costs range button {string} is visible',
  async ({ page }, name: string) => {
    if (!isRange(name)) {
      throw new Error(`Unknown Usage range "${name}". Known: 7 days, 30 days, 90 days, All time`);
    }
    const usage = new UsagePage(page);
    await expect(usage.rangeButton(name)).toBeVisible();
  },
);

Then(
  'the Usage and Costs range button {string} is marked active',
  async ({ page }, name: string) => {
    if (!isRange(name)) {
      throw new Error(`Unknown Usage range "${name}".`);
    }
    const usage = new UsagePage(page);
    // Source toggles aria-pressed="true" on exactly one button at a time.
    await expect(usage.activeRangeButton(name)).toBeVisible();
  },
);

When(
  'I click the Usage and Costs range button {string}',
  async ({ page }, name: string) => {
    if (!isRange(name)) {
      throw new Error(`Unknown Usage range "${name}".`);
    }
    const usage = new UsagePage(page);
    await usage.rangeButton(name).click();
  },
);

Then(
  'the Usage and Costs metric card {string} is visible',
  async ({ page }, name: string) => {
    if (!isMetricCard(name)) {
      throw new Error(`Unknown Usage metric card "${name}".`);
    }
    const usage = new UsagePage(page);
    await expect(usage.metricCard(name)).toBeVisible();
  },
);

// Regression guard for the AdminUsageResponse field-name mismatch (fixed in
// PR #10): a frontend that reads stale keys would render zero placeholders
// even when the backend reports non-zero totals. The seed inserts exactly one
// COMPLETED job with token_usage (input: 150000, output: 50000) so these
// cards must contain a non-zero digit (e.g. "200K", "$0.06", "1").
Then(
  'the Usage and Costs metric card {string} shows a non-zero value',
  async ({ page }, name: string) => {
    if (!isMetricCard(name)) {
      throw new Error(`Unknown Usage metric card "${name}".`);
    }
    const usage = new UsagePage(page);
    const card = usage.metricCard(name);
    await expect(card).toBeVisible();
    if (name === 'Estimated Cost') {
      // Match "$<digits>.<digits>" with at least one non-zero digit anywhere.
      await expect(card).toContainText(/\$[\d.]*[1-9]/);
    } else {
      await expect(card).toContainText(/[1-9]/);
    }
  },
);

Then(
  'the Usage and Costs metric card {string} shows secondary text',
  async ({ page }, name: string) => {
    if (!isMetricCard(name)) {
      throw new Error(`Unknown Usage metric card "${name}".`);
    }
    const usage = new UsagePage(page);
    const card = usage.metricCard(name);
    await expect(card).toContainText(METRIC_CARD_SECONDARY_RE[name]);
  },
);

Then('the Top Repositories chart heading is visible', async ({ page }) => {
  const usage = new UsagePage(page);
  // The chart heading "Top Repositories" is rendered by SectionErrorBoundary
  // children — present only when `top_repos_by_tokens` is non-empty. The seed
  // (tests/e2e_seed/seed_playwright.py) inserts one COMPLETED job with
  // token_usage so the aggregate yields a populated chart.
  await expect(usage.topRepositoriesChartHeading).toBeVisible();
});

Then(
  'the Usage by Model section shows the empty-state placeholder',
  async ({ page }) => {
    const usage = new UsagePage(page);
    // @known-gap: 00-index.md:135 — backend `usage_by_model` always returns [].
    // SectionErrorBoundary renders EmptyState with "No model usage data".
    await expect(usage.usageByModelEmptyState).toBeVisible();
  },
);

Then('the Cost Efficiency Tip banner is visible', async ({ page }) => {
  const usage = new UsagePage(page);
  await expect(usage.costEfficiencyTip).toBeVisible();
});

Then('no console errors were logged during Usage and Costs page load', async ({ page }) => {
  const errors = CONSOLE_ERRORS.get(page) ?? [];
  expect(
    errors,
    `Expected no console errors during /admin/usage load, got:\n${errors.join('\n')}`,
  ).toEqual([]);
});
