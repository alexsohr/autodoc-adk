import type { Browser, Page } from '@playwright/test';
// IMPORTANT: extend playwright-bdd's `test`, not @playwright/test's base.
// createBdd() requires it. The bdd `test` is itself an extension of
// @playwright/test, so existing specs/0N-*.spec.ts that import via
// fixtures/test.ts continue to work unchanged.
import { test as base } from 'playwright-bdd';

export type Role = 'admin' | 'developer' | 'viewer';

export type RoleFixtures = {
  asAdmin: Page;
  asDeveloper: Page;
  asViewer: Page;
};

async function pageWithRole(browser: Browser, role: Role): Promise<Page> {
  const ctx = await browser.newContext({
    extraHTTPHeaders: {
      'X-Forwarded-User': `e2e-${role}@test`,
      'X-Forwarded-Email': `e2e-${role}@test`,
      'X-Forwarded-Role': role,
    },
  });
  return ctx.newPage();
}

export const authTest = base.extend<RoleFixtures>({
  asAdmin: async ({ browser }, use) => {
    const p = await pageWithRole(browser, 'admin');
    await use(p);
    await p.context().close();
  },
  asDeveloper: async ({ browser }, use) => {
    const p = await pageWithRole(browser, 'developer');
    await use(p);
    await p.context().close();
  },
  asViewer: async ({ browser }, use) => {
    const p = await pageWithRole(browser, 'viewer');
    await use(p);
    await p.context().close();
  },
});
