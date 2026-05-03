import type { Page, Locator } from '@playwright/test';

export class AddRepoDialog {
  constructor(private readonly page: Page) {}
  readonly dialog:     Locator = this.page.getByRole('dialog', { name: /Add Repository/i });
  readonly urlInput:   Locator = this.dialog.getByLabel(/URL/i);
  readonly submit:     Locator = this.dialog.getByRole('button', { name: /Add Repository/i });
  readonly cancel:     Locator = this.dialog.getByRole('button', { name: /Cancel/i });
  readonly addRowBtn:  Locator = this.dialog.getByRole('button', { name: /\+\s*Add row/i });
  readonly removeRowButtons: Locator = this.dialog.getByRole('button', { name: /Remove/i });
}
