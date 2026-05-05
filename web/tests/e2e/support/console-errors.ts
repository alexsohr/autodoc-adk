import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

const CONSOLE_ERRORS = new WeakMap<Page, string[]>();

/**
 * Register a console listener on the page that records `error`-level
 * messages into a WeakMap keyed by Page. Call BEFORE the navigation that
 * should be monitored. Errors collected here can be asserted via
 * expectNoConsoleErrors(page).
 */
export function trackConsoleErrors(page: Page): void {
  CONSOLE_ERRORS.set(page, []);
  page.on('console', msg => {
    if (msg.type() === 'error') {
      CONSOLE_ERRORS.get(page)?.push(msg.text());
    }
  });
}

/**
 * Assert that no console errors were recorded for `page` since
 * trackConsoleErrors(page) was last called. Throws via expect().
 */
export function expectNoConsoleErrors(page: Page): void {
  const errors = CONSOLE_ERRORS.get(page) ?? [];
  expect(errors, `console errors logged: ${errors.join('\n')}`).toEqual([]);
}
