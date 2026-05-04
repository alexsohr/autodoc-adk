import { test as base, type Browser, type Page } from '@playwright/test';

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
