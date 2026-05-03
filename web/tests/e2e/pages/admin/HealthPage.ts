import type { Page, Locator } from '@playwright/test';

type ServiceCardName = 'API Cluster' | 'Prefect Server' | 'PostgreSQL' | 'Active Workers';

export class HealthPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/admin/health');
    await this.heading.waitFor();
  }

  readonly heading:        Locator = this.page.getByRole('heading', { name: /Infrastructure Snapshot/i });
  readonly workPoolsTable: Locator = this.page.getByRole('table', { name: /Work Pools/i });

  serviceCard(name: ServiceCardName): Locator {
    return this.page.getByRole('article').filter({ hasText: name });
  }
}
