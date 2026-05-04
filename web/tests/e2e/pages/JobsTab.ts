import type { Page, Locator } from '@playwright/test';

type FilterPillName = 'All' | 'Running' | 'Completed' | 'Failed' | 'Cancelled' | 'Pending';

const PILL_VALUE: Record<FilterPillName, string> = {
  'All':       '',
  'Running':   'RUNNING',
  'Completed': 'COMPLETED',
  'Failed':    'FAILED',
  'Cancelled': 'CANCELLED',
  'Pending':   'PENDING',
};

export class JobsTab {
  constructor(private readonly page: Page) {}
  readonly dryRunCheckbox:    Locator = this.page.getByTestId('jobs-dry-run-checkbox');
  readonly fullGenButton:     Locator = this.page.getByTestId('jobs-full-generation-button');
  readonly incrementalButton: Locator = this.page.getByTestId('jobs-incremental-button');
  readonly completedSection:  Locator = this.page.getByTestId('jobs-section-completed');
  readonly failedSection:     Locator = this.page.getByTestId('jobs-section-failed');
  readonly cancelledSection:  Locator = this.page.getByTestId('jobs-section-cancelled');

  filterPill(name: FilterPillName): Locator {
    return this.page.getByTestId(`filter-tab-${PILL_VALUE[name]}`);
  }
}
