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
  readonly costEfficiencyTip: Locator = this.page.getByTestId('usage-cost-efficiency-tip');

  rangeButton(name: Range): Locator {
    return this.page.getByTestId(`usage-range-${RANGE_SLUG[name]}`);
  }

  metricCard(name: MetricCard): Locator {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    return this.page.getByTestId(`usage-metric-card-${slug}`);
  }
}
