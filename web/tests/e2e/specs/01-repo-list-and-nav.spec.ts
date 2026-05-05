import { test, expect } from '../fixtures/test';
import { RepoListPage } from '../pages/RepoListPage';
import { REPOS } from '../support/seed-data';

// Source: docs/ui/01-repository-list-and-navigation.md
// Scenarios: docs/ui/test-scenarios/01-repo-list-and-nav.test-scenarios.md

test.describe('01 — Repository List & Global Navigation', () => {

  // ─── WORKED EXAMPLE — implementation pattern reference ───
  test('PTS-1.1: full page load and render', async ({ page }) => {
    const repos = new RepoListPage(page);
    await repos.goto();

    await expect(page).toHaveTitle(/AutoDoc/);
    await expect(repos.heading).toBeVisible();
    await expect(repos.subtitle).toContainText(/\d+ repositories registered/);

    for (const tab of ['All', 'Healthy', 'Running', 'Failed', 'Pending'] as const) {
      await expect(repos.filterTab(tab)).toBeVisible();
    }
    await expect(repos.card(REPOS.digitalClock.name)).toBeVisible();
    await expect(repos.addRepoCtaCard).toBeVisible();
    await expect(repos.paginationFooter).toContainText(/Showing \d+-\d+ of \d+/);
    await expect(repos.sidebar.repositoriesLink).toHaveAttribute('aria-current', 'page');
  });

  // ─── SKIPPED — implement during the per-feature opsx change ───
  test.skip('PTS-1.2: end-to-end Add Repository flow', async ({ page }) => {
    // Acceptance: dialog opens with URL input, provider auto-detect, branch
    // mapping rows, submit disabled when URL empty, enabled when URL filled
    // and ≥1 mapping. Adding a 2nd row enables Remove on all rows.
  });

  test.skip('PTS-1.3: filter + search interaction', async ({ page }) => {
    // Acceptance: filter tabs narrow grid; typing further narrows by full_name;
    // pagination footer reflects filtered count; clearing search restores cards
    // matching the active filter.
    // Note: 00-index.md PTS-1.3 observation flagged a count-mismatch bug on the
    // Pending tab; assert spec behavior, expect failure.
  });

  test.skip('PTS-1.4: navigation from card to workspace', async ({ page }) => {
    // Acceptance: click card → URL changes to /repos/{id}; breadcrumb shows
    // "Repositories > {name}"; metric cards load with data; tab bar appears;
    // global search placeholder changes to "Search documentation...".
  });

  test.skip('PTS-1.5: global search from home page', async ({ page }) => {
    // Acceptance: typing in TopBar search debounces and triggers a search;
    // dropdown appears with matching docs OR "No results found".
  });

  test.skip('PTS-1.6: sidebar navigation from home', async ({ asDeveloper }) => {
    // Acceptance: System Health → /admin/health, All Jobs → /admin/jobs,
    // Repositories → /. Active sidebar link reflects current route.
    // Uses asDeveloper because admin sidebar links are role-gated.
  });
});
