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
  // Present only when the search boundary renders its error branch — used by
  // PTS-2.4 to assert the documented 503/Service-Unavailable fallback path.
  readonly errorState:   Locator = this.page.getByTestId('search-error-state');

  modeButton(name: SearchMode): Locator {
    return this.page.getByTestId(`filter-tab-${MODE_VALUE[name]}`);
  }
}
