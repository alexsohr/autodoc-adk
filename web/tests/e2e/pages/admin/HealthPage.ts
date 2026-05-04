import type { Page, Locator } from '@playwright/test';

type ServiceCardName = 'API Cluster' | 'Prefect Server' | 'PostgreSQL' | 'Active Workers';

export class HealthPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/admin/health');
    await this.heading.waitFor();
  }

  readonly heading:        Locator = this.page.getByRole('heading', { name: /Infrastructure Snapshot/i });
  readonly workPoolsTable: Locator = this.page.getByTestId('work-pools-table');

  serviceCard(name: ServiceCardName): Locator {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    return this.page.getByTestId(`health-service-card-${slug}`);
  }
}
