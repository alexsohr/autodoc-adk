import type { Page, Locator } from '@playwright/test';

export class TopBar {
  constructor(private readonly page: Page) {}
  readonly logoLink:          Locator = this.page.getByRole('link', { name: /AutoDoc/i });
  readonly globalSearch:      Locator = this.page.getByTestId('topbar-global-search');
  readonly notificationsBell: Locator = this.page.getByRole('button', { name: /notifications/i });
  readonly userAvatar:        Locator = this.page.getByTestId('topbar-user');
}
