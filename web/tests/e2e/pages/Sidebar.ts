import type { Page, Locator } from '@playwright/test';

export class Sidebar {
  constructor(private readonly page: Page) {}
  readonly repositoriesLink: Locator = this.page.getByTestId('sidebar-link-repositories');
  readonly systemHealthLink: Locator = this.page.getByTestId('sidebar-link-system-health');
  readonly allJobsLink:      Locator = this.page.getByTestId('sidebar-link-all-jobs');
  readonly usageLink:        Locator = this.page.getByTestId('sidebar-link-usage-costs');
  readonly mcpLink:          Locator = this.page.getByTestId('sidebar-link-mcp-servers');
}
