import type { Page, Locator } from '@playwright/test';

type SearchMode = 'Hybrid' | 'Semantic' | 'Full Text';

const MODE_VALUE: Record<SearchMode, string> = {
  'Hybrid': 'hybrid',
  'Semantic': 'semantic',
  'Full Text': 'fulltext',
};

export class SearchTab {
  constructor(private readonly page: Page) {}
  readonly input:        Locator = this.page.getByTestId('search-tab-input');
  readonly searchButton: Locator = this.page.getByTestId('search-tab-submit');

  modeButton(name: SearchMode): Locator {
    return this.page.getByTestId(`filter-tab-${MODE_VALUE[name]}`);
  }
}
