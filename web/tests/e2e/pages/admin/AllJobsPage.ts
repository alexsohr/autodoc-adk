import type { Page, Locator } from '@playwright/test';

type FilterPill = 'All' | 'Running' | 'Completed' | 'Failed' | 'Pending';

const PILL_VALUE: Record<FilterPill, string> = {
  'All':       'all',
  'Running':   'running',
  'Completed': 'completed',
  'Failed':    'failed',
  'Pending':   'pending',
};

export class AllJobsPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/admin/jobs');
    await this.heading.waitFor();
  }

  readonly heading:     Locator = this.page.getByRole('heading', { name: /^All Jobs$/ });
  readonly jobsTable:   Locator = this.page.getByTestId('all-jobs-table');
  readonly searchInput: Locator = this.page.getByTestId('all-jobs-search');

  filterPill(name: FilterPill): Locator {
    return this.page.getByTestId(`filter-tab-${PILL_VALUE[name]}`);
  }
}
