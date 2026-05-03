import type { Page, Locator } from '@playwright/test';

export class Sidebar {
  constructor(private readonly page: Page) {}
  readonly repositoriesLink: Locator = this.page.getByRole('link', { name: 'Repositories', exact: true });
  readonly systemHealthLink: Locator = this.page.getByRole('link', { name: 'System Health' });
  readonly allJobsLink:      Locator = this.page.getByRole('link', { name: 'All Jobs' });
  readonly usageLink:        Locator = this.page.getByRole('link', { name: 'Usage & Costs' });
  readonly mcpLink:          Locator = this.page.getByRole('link', { name: 'MCP Servers' });
}
