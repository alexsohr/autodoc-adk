import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { Then, When } from './bdd';
import { HealthPage } from '../pages/admin/HealthPage';

// ─────────────────────────────────────────────────────────────────────────────
// Console-error tracking
//
// PTS-3.1's acceptance criteria from docs/ui/00-index.md ends with "no console
// errors". To assert that without touching support/hooks.ts, we keep a per-Page
// WeakMap of error messages. The "When I open the System Health page" step
// registers a `console` listener BEFORE navigation, so any error logged during
// initial render is captured. The "Then no console errors are logged" step
// reads from the same WeakMap.
//
// WeakMap (rather than a module-level Map) keyed on the Page lets entries
// disappear automatically when the BrowserContext closes — important because
// the @as-developer fixture builds a fresh context per scenario.
// ─────────────────────────────────────────────────────────────────────────────
const CONSOLE_ERRORS = new WeakMap<Page, string[]>();

// /admin/health upstream depends on a live Prefect server with seeded work
// pools. In the CI/local stub environment Prefect isn't reachable, so the
// API returns `worker_pools: []` and the DataTable shows its empty state
// (no `<thead>`/column headers). To assert the column-header acceptance
// bullet without faking the source render, we shim the response inline with
// two representative pools mirroring the data observed in 00-index.md
// § PTS-3.1 (k8s-pool / orchestrator-pool). We intentionally inline this in
// the step file rather than `support/api-stubs.ts` — the shim is specific
// to PTS-3.1 and out of scope for the shared stubs module.
const ADMIN_HEALTH_SHIM = {
  api_uptime_seconds: 1234.5,
  api_latency_ms: 42,
  prefect_status: 'healthy',
  prefect_pool_count: 2,
  database: {
    version: 'PostgreSQL 18.2 (E2E shim)',
    pgvector_installed: true,
    storage_mb: '17.5',
  },
  worker_pools: [
    { name: 'k8s-pool',          type: 'kubernetes', status: 'READY', concurrency_limit: 50 },
    { name: 'orchestrator-pool', type: 'kubernetes', status: 'READY', concurrency_limit: 10 },
  ],
};

async function gotoHealthWithConsoleTracking(page: Page): Promise<void> {
  const errors: string[] = [];
  CONSOLE_ERRORS.set(page, errors);
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });
  // Match XHR/fetch requests to the API endpoint only — NOT the SPA route at
  // `/admin/health` that we're about to navigate to. We narrow by request type
  // (`xhr`/`fetch`) and by path equality to dodge the URL collision.
  await page.route(/\/admin\/health(?:\?|$)/, (route, request) => {
    const type = request.resourceType();
    if (type !== 'xhr' && type !== 'fetch') {
      return route.continue();
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(ADMIN_HEALTH_SHIM),
    });
  });
  const health = new HealthPage(page);
  await health.goto();
}

type ServiceCardName = 'API Cluster' | 'Prefect Server' | 'PostgreSQL' | 'Active Workers';
type PoolColumn      = 'Pool Name' | 'Type' | 'Concurrency Limit' | 'Status';
type FooterStat      = 'Last Sync' | 'Encrypted' | 'Throughput' | 'History';

// Map the human-readable column header label to the React column `key`,
// which is what `data-testid="datatable-header-${col.key}"` is built from
// (see `poolColumns` in src/pages/admin/SystemHealthPage.tsx).
const POOL_COLUMN_KEY: Record<PoolColumn, 'name' | 'type' | 'concurrency_limit' | 'status'> = {
  'Pool Name':         'name',
  'Type':              'type',
  'Concurrency Limit': 'concurrency_limit',
  'Status':            'status',
};

// Footer tile label → testid suffix. Mirrors the slug derivation in
// SystemHealthPage.tsx (lowercase, non-alphanumerics → "-").
const FOOTER_SLUG: Record<FooterStat, 'last-sync' | 'encrypted' | 'throughput' | 'history'> = {
  'Last Sync':  'last-sync',
  'Encrypted':  'encrypted',
  'Throughput': 'throughput',
  'History':    'history',
};

// ─────────────────────────────────────────────────────────────────────────────
// PTS-3.1 — Implemented steps (System Health full page)
// ─────────────────────────────────────────────────────────────────────────────

When('I open the System Health page', async ({ page }) => {
  await gotoHealthWithConsoleTracking(page);
});

Then('the System Health heading is visible', async ({ page }) => {
  const health = new HealthPage(page);
  await expect(health.heading).toBeVisible();
});

Then('the System Health subtitle is visible', async ({ page }) => {
  const health = new HealthPage(page);
  await expect(health.subtitle).toBeVisible();
});

Then(
  'the System Health service card {string} is visible with a status badge',
  async ({ page }, name: string) => {
    const health = new HealthPage(page);
    await expect(health.serviceCard(name as ServiceCardName)).toBeVisible();
    await expect(health.serviceCardStatusBadge(name as ServiceCardName)).toBeVisible();
  },
);

Then('the Work Pools table is visible', async ({ page }) => {
  const health = new HealthPage(page);
  await expect(health.workPoolsTable).toBeVisible();
});

Then(
  'the Work Pools table column header {string} is visible',
  async ({ page }, header: string) => {
    const health = new HealthPage(page);
    const key = POOL_COLUMN_KEY[header as PoolColumn];
    if (!key) {
      throw new Error(
        `Unknown Work Pools column header "${header}". Known: ${Object.keys(POOL_COLUMN_KEY).join(', ')}`,
      );
    }
    await expect(health.workPoolsColumnHeader(key)).toBeVisible();
  },
);

Then('the Worker Capacity section is visible', async ({ page }) => {
  const health = new HealthPage(page);
  await expect(health.workerCapacitySection).toBeVisible();
});

Then('the Worker Capacity Current Peak stat is visible', async ({ page }) => {
  const health = new HealthPage(page);
  await expect(health.capacityCurrentPeak).toBeVisible();
});

Then('the Worker Capacity Avg Wait stat is visible', async ({ page }) => {
  const health = new HealthPage(page);
  await expect(health.capacityAvgWait).toBeVisible();
});

Then('the Scale On-Demand CTA banner is visible', async ({ page }) => {
  const health = new HealthPage(page);
  await expect(health.ctaBanner).toBeVisible();
});

Then('the Scale On-Demand banner Configure Auto-Scale button is visible', async ({ page }) => {
  const health = new HealthPage(page);
  await expect(health.ctaConfigureBtn).toBeVisible();
});

Then('the Scale On-Demand banner View Logs button is visible', async ({ page }) => {
  const health = new HealthPage(page);
  await expect(health.ctaViewLogsBtn).toBeVisible();
});

Then(
  'the System Health footer stat {string} is visible',
  async ({ page }, label: string) => {
    const health = new HealthPage(page);
    const slug = FOOTER_SLUG[label as FooterStat];
    if (!slug) {
      throw new Error(
        `Unknown System Health footer stat "${label}". Known: ${Object.keys(FOOTER_SLUG).join(', ')}`,
      );
    }
    await expect(health.footerStat(slug)).toBeVisible();
  },
);

Then('no console errors were logged during page load', async ({ page }) => {
  const errors = CONSOLE_ERRORS.get(page) ?? [];
  expect(
    errors,
    `Expected no console errors during /admin/health load, got:\n${errors.join('\n')}`,
  ).toEqual([]);
});
