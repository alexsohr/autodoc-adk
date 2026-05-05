import type { Page, Locator } from '@playwright/test';

export const byHeading = (page: Page, name: string | RegExp): Locator =>
  page.getByRole('heading', { name });

export const byTab = (page: Page, name: string | RegExp): Locator =>
  page.getByRole('tab', { name });

export const byButton = (page: Page, name: string | RegExp): Locator =>
  page.getByRole('button', { name });
