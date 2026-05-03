import type { Page, Locator } from '@playwright/test';

type FilterPillName = 'All' | 'Running' | 'Completed' | 'Failed' | 'Cancelled' | 'Pending';

export class JobsTab {
  constructor(private readonly page: Page) {}
  readonly dryRunCheckbox:    Locator = this.page.getByRole('checkbox', { name: /Dry Run/i });
  readonly fullGenButton:     Locator = this.page.getByRole('button', { name: /Full Generation/i });
  readonly incrementalButton: Locator = this.page.getByRole('button', { name: /Incremental/i });
  readonly completedSection:  Locator = this.page.getByRole('region', { name: /Completed/i });
  readonly failedSection:     Locator = this.page.getByRole('region', { name: /Failed/i });
  readonly cancelledSection:  Locator = this.page.getByRole('region', { name: /Cancelled/i });

  filterPill(name: FilterPillName): Locator {
    return this.page.getByRole('button', { name: new RegExp(`^${name}\\(`) });
  }
}
