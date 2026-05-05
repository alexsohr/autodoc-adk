import type { Page, Locator } from '@playwright/test';

type IntegrationTab = 'VS Code' | 'Claude Code' | 'Generic MCP Client';
type SecuritySection = 'Transport' | 'Authentication' | 'Rate Limiting' | 'Data Access';

const INTEGRATION_SLUG: Record<IntegrationTab, string> = {
  'VS Code':            'vscode',
  'Claude Code':        'claude-code',
  'Generic MCP Client': 'generic',
};

const SECURITY_SLUG: Record<SecuritySection, string> = {
  'Transport':      'transport',
  'Authentication': 'authentication',
  'Rate Limiting':  'rate-limiting',
  'Data Access':    'data-access',
};

export class McpPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/admin/mcp');
    await this.heading.waitFor();
  }

  readonly heading:          Locator = this.page.getByRole('heading', { name: /MCP Servers/i });
  readonly serverStatusCard: Locator = this.page.getByTestId('mcp-server-status-card');

  integrationTab(name: IntegrationTab): Locator {
    return this.page.getByTestId(`mcp-integration-tab-${INTEGRATION_SLUG[name]}`);
  }

  securitySection(name: SecuritySection): Locator {
    return this.page.getByTestId(`mcp-security-${SECURITY_SLUG[name]}`);
  }
}
