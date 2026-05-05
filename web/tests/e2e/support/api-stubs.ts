import type { Page } from '@playwright/test';

/** Force /documents/{id}/search to return 503 (matches the PTS-2.4 environment-limited observation). */
export async function stubSearch503(page: Page): Promise<void> {
  await page.route('**/documents/*/search**', route =>
    route.fulfill({ status: 503, body: JSON.stringify({ detail: 'Service Unavailable' }) }),
  );
}

/** Force /admin/health to a degraded response. */
export async function stubHealthDegraded(page: Page): Promise<void> {
  await page.route('**/admin/health', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'degraded', services: [] }),
    }),
  );
}
