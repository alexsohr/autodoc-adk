import type { Page, Locator } from '@playwright/test';

type SubTab = 'General' | 'Branches' | 'Webhooks' | 'AutoDoc Config' | 'Danger Zone';

const SUBTAB_SLUG: Record<SubTab, string> = {
  'General':        'general',
  'Branches':       'branches',
  'Webhooks':       'webhooks',
  'AutoDoc Config': 'autodoc-config',
  'Danger Zone':    'danger-zone',
};

export class SettingsTab {
  constructor(private readonly page: Page) {}
  subTab(name: SubTab): Locator {
    return this.page.getByTestId(`settings-subtab-${SUBTAB_SLUG[name]}`);
  }
  readonly generalSection: Locator = this.page.getByTestId('settings-section-general');
  readonly dangerZone:     Locator = this.page.getByTestId('settings-section-danger-zone');
}
