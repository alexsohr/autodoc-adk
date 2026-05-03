import type { Page, Locator } from '@playwright/test';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { AddRepoDialog } from './AddRepoDialog';

type FilterTabName = 'All' | 'Healthy' | 'Running' | 'Failed' | 'Pending';

export class RepoListPage {
  readonly topBar: TopBar;
  readonly sidebar: Sidebar;

  constructor(private readonly page: Page) {
    this.topBar = new TopBar(page);
    this.sidebar = new Sidebar(page);
  }

  async goto(): Promise<void> {
    await this.page.goto('/');
    await this.heading.waitFor();
  }

  readonly heading:          Locator = this.page.getByRole('heading', { name: 'Repositories', exact: true });
  readonly subtitle:         Locator = this.page.getByText(/repositories registered/);
  readonly addRepoButton:    Locator = this.page.getByRole('button', { name: /Add Repo$/ });
  readonly addRepoCtaCard:   Locator = this.page.getByRole('button', { name: /Add Repository/i });
  readonly paginationFooter: Locator = this.page.getByText(/Showing \d+-\d+ of \d+/);

  filterTab(name: FilterTabName): Locator {
    return this.page.getByRole('tab', { name: new RegExp(`^${name}\\b`) });
  }

  card(repoName: string): Locator {
    return this.page.getByRole('article').filter({ hasText: repoName });
  }

  async openAddRepoDialog(): Promise<AddRepoDialog> {
    await this.addRepoButton.click();
    const dialog = new AddRepoDialog(this.page);
    await dialog.dialog.waitFor();
    return dialog;
  }
}
