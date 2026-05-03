import type { Page, Locator } from '@playwright/test';

type SearchMode = 'Hybrid' | 'Semantic' | 'Full Text';

export class SearchTab {
  constructor(private readonly page: Page) {}
  readonly input:        Locator = this.page.getByPlaceholder(/Search documentation/);
  readonly searchButton: Locator = this.page.getByRole('button', { name: /^Search$/ });

  modeButton(name: SearchMode): Locator {
    return this.page.getByRole('button', { name: new RegExp(`^${name}$`) });
  }
}
