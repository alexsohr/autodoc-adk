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

  readonly breadcrumb:       Locator = this.page.getByRole('navigation', { name: /breadcrumb/i });
  readonly runFullGenButton: Locator = this.page.getByRole('button', { name: /Run Full Generation/i });

  metricCard(name: MetricCardName): Locator {
    return this.page.getByRole('article').filter({ hasText: name });
  }

  tab(name: TabName): Locator {
    return this.page.getByRole('tab', { name: new RegExp(`^${name}\\b`) });
  }
}
