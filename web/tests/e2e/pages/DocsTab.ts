import type { Page, Locator } from '@playwright/test';

export class DocsTab {
  constructor(private readonly page: Page) {}
  readonly scopeSelector: Locator = this.page.getByTestId('docs-scope-selector');
  readonly docTree:       Locator = this.page.getByTestId('docs-tree');
  readonly qualityPill:   Locator = this.page.getByTestId('docs-quality-pill');
  readonly nextButton:    Locator = this.page.getByTestId('docs-nav-next');
  readonly prevButton:    Locator = this.page.getByTestId('docs-nav-prev');
  readonly mermaid:       Locator = this.page.getByTestId('docs-mermaid');

  treeItem(name: string | RegExp): Locator {
    return this.page.getByRole('treeitem', { name });
  }
}
