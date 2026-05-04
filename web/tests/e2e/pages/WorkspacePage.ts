import type { Page, Locator } from '@playwright/test';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';

type TabName = 'Overview' | 'Docs' | 'Search' | 'Chat' | 'Jobs' | 'Quality' | 'Settings';
type MetricCardName = 'Doc Pages' | 'Avg Quality' | 'Scopes' | 'Last Generated';

export class WorkspacePage {
  readonly topBar: TopBar;
  readonly sidebar: Sidebar;

  constructor(private readonly page: Page) {
    this.topBar = new TopBar(page);
    this.sidebar = new Sidebar(page);
  }

  async goto(repoId: string): Promise<void> {
    await this.page.goto(`/repos/${repoId}`);
    await this.breadcrumb.waitFor();
  }

  readonly breadcrumb:       Locator = this.page.getByTestId('repo-breadcrumb');
  readonly runFullGenButton: Locator = this.page.getByTestId('workspace-run-full-generation');

  metricCard(name: MetricCardName): Locator {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    return this.page.getByTestId(`overview-metric-card-${slug}`);
  }

  tab(name: TabName): Locator {
    return this.page.getByTestId(`workspace-tab-${name.toLowerCase().replace(/\s+/g, '-')}`);
  }
}
