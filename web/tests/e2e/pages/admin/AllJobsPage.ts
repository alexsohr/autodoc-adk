import type { Page, Locator } from '@playwright/test';

type FilterPill = 'All' | 'Running' | 'Completed' | 'Failed' | 'Pending';

export class AllJobsPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/admin/jobs');
    await this.heading.waitFor();
  }

  readonly heading:     Locator = this.page.getByRole('heading', { name: /^All Jobs$/ });
  readonly jobsTable:   Locator = this.page.getByRole('table');
  readonly searchInput: Locator = this.page.getByPlaceholder(/Search by repository/i);

  filterPill(name: FilterPill): Locator {
    return this.page.getByRole('button', { name: new RegExp(`^${name}\\(`) });
  }
}
