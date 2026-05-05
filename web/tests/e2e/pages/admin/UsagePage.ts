import type { Page, Locator } from '@playwright/test';

type Range = '7 days' | '30 days' | '90 days' | 'All time';
type MetricCard = 'Total Tokens' | 'Estimated Cost' | 'Total Jobs';

const RANGE_SLUG: Record<Range, string> = {
  '7 days':   '7-days',
  '30 days':  '30-days',
  '90 days':  '90-days',
  'All time': 'all-time',
};

export class UsagePage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/admin/usage');
    await this.heading.waitFor();
  }

  readonly heading:           Locator = this.page.getByRole('heading', { name: /Usage & Costs/i });
  readonly subtitle:          Locator = this.page.getByTestId('usage-subtitle');
  readonly costEfficiencyTip: Locator = this.page.getByTestId('usage-cost-efficiency-tip');
  // The "Top Repositories" chart (rendered when seeded usage data exists).
  readonly topRepositoriesChartHeading: Locator = this.page.getByRole('heading', { name: /Top Repositories/i });
  // Empty-state placeholder for the "Usage by Model" chart. The backend
  // currently returns `usage_by_model: []` (00-index.md § Known Gaps), so the
  // SectionErrorBoundary renders the EmptyState component with this message.
  readonly usageByModelEmptyState: Locator = this.page.getByText(/No model usage data/i);

  rangeButton(name: Range): Locator {
    return this.page.getByTestId(`usage-range-${RANGE_SLUG[name]}`);
  }

  // The currently-active range button. Source toggles `aria-pressed="true"` on
  // exactly one button at a time (UsageCostsPage.tsx). Only one will match.
  activeRangeButton(name: Range): Locator {
    return this.page.locator(
      `[data-testid="usage-range-${RANGE_SLUG[name]}"][aria-pressed="true"]`,
    );
  }

  metricCard(name: MetricCard): Locator {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    return this.page.getByTestId(`usage-metric-card-${slug}`);
  }
}
