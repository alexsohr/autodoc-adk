import { expect } from '@playwright/test';
import { Given, Then } from './bdd';

Given('I am on the AutoDoc dashboard home page', async ({ page }) => {
  await page.goto('/');
});

Then('the page title contains {string}', async ({ page }, text: string) => {
  await expect(page).toHaveTitle(new RegExp(text));
});

// Generic URL regex assertion — used by any feature that wants to assert the
// browser URL matches a documented pattern. Pattern argument is a JS RegExp
// source string (no leading/trailing slash, no flags).
Then('the URL matches the pattern {string}', async ({ page }, pattern: string) => {
  await expect(page).toHaveURL(new RegExp(pattern));
});
