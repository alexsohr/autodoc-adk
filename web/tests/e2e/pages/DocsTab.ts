import type { Page, Locator } from '@playwright/test';

export class DocsTab {
  constructor(private readonly page: Page) {}
  readonly scopeSelector: Locator = this.page.getByRole('combobox', { name: /scope/i });
  readonly docTree:       Locator = this.page.getByRole('tree');
  readonly qualityPill:   Locator = this.page.getByText(/^\d+(\.\d+)?\/10$/);
  readonly nextButton:    Locator = this.page.getByRole('button', { name: /^Next/ });
  readonly prevButton:    Locator = this.page.getByRole('button', { name: /^Previous/ });

  treeItem(name: string | RegExp): Locator {
    return this.page.getByRole('treeitem', { name });
  }
}
