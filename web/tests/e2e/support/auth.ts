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

// Map a scenario tag to the role it requests, or null for the admin default.
// `@as-admin` is intentionally NOT in this map — admin is the implicit default
// (configured via `use.extraHTTPHeaders` in playwright.config.ts).
function roleFromTags(tags: string[] | undefined): Role | null {
  if (!tags || tags.length === 0) return null;
  if (tags.includes('@as-developer')) return 'developer';
  if (tags.includes('@as-viewer')) return 'viewer';
  return null;
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
  // Override the default `page` fixture so BDD scenarios can opt into a
  // role-specific BrowserContext via scenario tags. `$tags` is a fixture
  // injected by playwright-bdd (see playwright-bdd/dist/runtime/bddTestFixtures.d.ts).
  // When `@as-developer` or `@as-viewer` is present, we build a fresh context
  // with role-specific X-Forwarded-* headers and yield its page; otherwise we
  // fall through to the default `page` (admin via playwright.config.ts:use).
  page: async ({ $tags, browser, page }, use) => {
    const role = roleFromTags($tags);
    if (role === null) {
      await use(page);
      return;
    }
    const rolePage = await pageWithRole(browser, role);
    await use(rolePage);
    await rolePage.context().close();
  },
});
