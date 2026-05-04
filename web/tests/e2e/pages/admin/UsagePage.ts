import type { Page, Locator } from '@playwright/test';

type Range = '7 days' | '30 days' | '90 days' | 'All time';
type MetricCard = 'Total Tokens' | 'Estimated Cost' | 'Total Jobs';

export class UsagePage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/admin/usage');
    await this.heading.waitFor();
  }

  readonly heading: Locator = this.page.getByRole('heading', { name: /Usage & Costs/i });

  rangeButton(name: Range): Locator {
    return this.page.getByRole('button', { name: new RegExp(`^${name}$`) });
  }

  metricCard(name: MetricCard): Locator {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    return this.page.getByTestId(`usage-metric-card-${slug}`);
  }
}
