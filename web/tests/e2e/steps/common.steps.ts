import { expect } from '@playwright/test';
import { Given, Then } from './bdd';

Given('I am on the AutoDoc dashboard home page', async ({ page }) => {
  await page.goto('/');
});

Then('the page title contains {string}', async ({ page }, text: string) => {
  await expect(page).toHaveTitle(new RegExp(text));
});
