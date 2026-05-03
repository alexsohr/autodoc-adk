import type { Page, Locator } from '@playwright/test';

type IntegrationTab = 'VS Code' | 'Claude Code' | 'Generic MCP Client';

export class McpPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/admin/mcp');
    await this.heading.waitFor();
  }

  readonly heading:          Locator = this.page.getByRole('heading', { name: /MCP Servers/i });
  readonly serverStatusCard: Locator = this.page.getByRole('article').filter({ hasText: /Server Status/i });

  integrationTab(name: IntegrationTab): Locator {
    return this.page.getByRole('tab', { name: new RegExp(name) });
  }
}
