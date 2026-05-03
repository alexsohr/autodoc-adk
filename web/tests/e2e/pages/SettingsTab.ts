import type { Page, Locator } from '@playwright/test';

type SubTab = 'General' | 'Branches' | 'Webhooks' | 'AutoDoc Config' | 'Danger Zone';

export class SettingsTab {
  constructor(private readonly page: Page) {}
  subTab(name: SubTab): Locator {
    return this.page.getByRole('tab', { name: new RegExp(`^${name}\\b`) });
  }
  readonly generalSection: Locator = this.page.getByRole('region', { name: /Repository Info|General/i });
  readonly dangerZone:     Locator = this.page.getByRole('region', { name: /Danger Zone/i });
}
