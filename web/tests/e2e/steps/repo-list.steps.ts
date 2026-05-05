import { expect } from '@playwright/test';
import { Then, When } from './bdd';
import { RepoListPage } from '../pages/RepoListPage';
import { TopBar } from '../pages/TopBar';
import { Sidebar } from '../pages/Sidebar';
import { REPOS, type SeedRepo } from '../support/seed-data';

// ─────────────────────────────────────────────────────────────────────────────
// Seed lookup helper
//
// Scenarios reference repositories by symbolic seed name (e.g. "digitalClock"),
// not by their displayed `name`. We resolve the symbolic name to the seed
// record here so step text stays stable when displayed names change.
// ─────────────────────────────────────────────────────────────────────────────
type SeedKey = keyof typeof REPOS;

function resolveSeedRepo(symbolic: string): SeedRepo {
  if (!(symbolic in REPOS)) {
    throw new Error(
      `Unknown seed repo "${symbolic}". Known keys: ${Object.keys(REPOS).join(', ')}`,
    );
  }
  return REPOS[symbolic as SeedKey];
}

// ─────────────────────────────────────────────────────────────────────────────
// PTS-1.1 — Implemented steps
// ─────────────────────────────────────────────────────────────────────────────

Then('the {string} heading is visible', async ({ page }, name: string) => {
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
});

Then(
  'the page subtitle indicates how many repositories are registered',
  async ({ page }) => {
    const repos = new RepoListPage(page);
    await expect(repos.subtitle).toContainText(/\d+ repositories registered/);
  },
);

Then('all five repository filter tabs are visible', async ({ page }) => {
  const repos = new RepoListPage(page);
  for (const tab of ['All', 'Healthy', 'Running', 'Failed', 'Pending'] as const) {
    await expect(repos.filterTab(tab)).toBeVisible();
  }
});

Then(
  'the {string} repository card is visible',
  async ({ page }, symbolic: string) => {
    const repos = new RepoListPage(page);
    const seed = resolveSeedRepo(symbolic);
    await expect(repos.card(seed.name)).toBeVisible();
  },
);

Then('the Add Repository CTA card is visible', async ({ page }) => {
  const repos = new RepoListPage(page);
  await expect(repos.addRepoCtaCard).toBeVisible();
});

Then(
  'the pagination footer matches the format {string}',
  async ({ page }, _format: string) => {
    // The {string} parameter ("Showing X-Y of Z") is documentation only —
    // the actual assertion uses the well-known regex from RepoListPage.
    void _format;
    const repos = new RepoListPage(page);
    await expect(repos.paginationFooter).toContainText(/Showing \d+-\d+ of \d+/);
  },
);

Then('the sidebar Repositories link is marked active', async ({ page }) => {
  const sidebar = new Sidebar(page);
  await expect(sidebar.repositoriesLink).toHaveAttribute('aria-current', 'page');
});

Then('the TopBar global search is visible', async ({ page }) => {
  const topBar = new TopBar(page);
  await expect(topBar.globalSearch).toBeVisible();
});

Then('the TopBar notifications bell is visible', async ({ page }) => {
  const topBar = new TopBar(page);
  await expect(topBar.notificationsBell).toBeVisible();
});

Then('the TopBar user avatar is visible', async ({ page }) => {
  const topBar = new TopBar(page);
  await expect(topBar.userAvatar).toBeVisible();
});

// ─────────────────────────────────────────────────────────────────────────────
// PTS-1.2..1.6 — Placeholder steps
//
// These scenarios are tagged @todo and skipped at runtime by support/hooks.ts.
// playwright-bdd codegen requires every step in every scenario to have a
// definition, even when the scenario will be skipped — so each placeholder
// below resolves immediately. They will be replaced with real implementations
// in the per-area PRs that remove the @todo tag.
// See features/README.md § Authoring a new feature.
// ─────────────────────────────────────────────────────────────────────────────

// PTS-1.2
When('I open the Add Repository dialog', async () => {
  // @todo: implemented in per-area PR for PTS-1.2
  await Promise.resolve();
});
Then(
  'the dialog shows a URL input, branch mapping section, and submit button',
  async () => {
    // @todo: implemented in per-area PR for PTS-1.2
    await Promise.resolve();
  },
);
Then(
  'the submit button is disabled while the URL field is empty',
  async () => {
    // @todo: implemented in per-area PR for PTS-1.2
    await Promise.resolve();
  },
);
When('I enter a GitHub repository URL', async () => {
  // @todo: implemented in per-area PR for PTS-1.2
  await Promise.resolve();
});
Then('the provider is auto-detected as {string}', async ({}, _provider: string) => {
  // @todo: implemented in per-area PR for PTS-1.2
  await Promise.resolve();
});
Then(
  'the submit button is enabled because the default branch mapping is complete',
  async () => {
    // @todo: implemented in per-area PR for PTS-1.2
    await Promise.resolve();
  },
);
When('I add a second branch mapping row', async () => {
  // @todo: implemented in per-area PR for PTS-1.2
  await Promise.resolve();
});
Then(
  'the Remove button on every branch mapping row is enabled',
  async () => {
    // @todo: implemented in per-area PR for PTS-1.2
    await Promise.resolve();
  },
);

// PTS-1.3
When('I click the {string} filter tab', async ({}, _tab: string) => {
  // @todo: implemented in per-area PR for PTS-1.3
  await Promise.resolve();
});
Then('only repositories with Pending status are displayed', async () => {
  // @todo: implemented in per-area PR for PTS-1.3 — see @known-gap on this scenario.
  await Promise.resolve();
});
When(
  'I type {string} into the repository search field',
  async ({}, _query: string) => {
    // @todo: implemented in per-area PR for PTS-1.3
    await Promise.resolve();
  },
);
Then(
  'only repositories whose full name matches {string} are displayed',
  async ({}, _query: string) => {
    // @todo: implemented in per-area PR for PTS-1.3
    await Promise.resolve();
  },
);
Then('the pagination footer reflects the filtered count', async () => {
  // @todo: implemented in per-area PR for PTS-1.3
  await Promise.resolve();
});
When('I clear the repository search field', async () => {
  // @todo: implemented in per-area PR for PTS-1.3
  await Promise.resolve();
});
Then(
  'all repository cards matching the active filter are restored',
  async () => {
    // @todo: implemented in per-area PR for PTS-1.3
    await Promise.resolve();
  },
);

// PTS-1.4
When(
  'I click the {string} repository card',
  async ({}, _symbolic: string) => {
    // @todo: implemented in per-area PR for PTS-1.4 — resolve via REPOS[symbolic].
    await Promise.resolve();
  },
);
Then('the URL changes to the repository workspace path', async () => {
  // @todo: implemented in per-area PR for PTS-1.4
  await Promise.resolve();
});
Then('the breadcrumb shows {string}', async ({}, _crumbs: string) => {
  // @todo: implemented in per-area PR for PTS-1.4
  await Promise.resolve();
});
Then(
  'the workspace header displays the repository name, status, and owner path',
  async () => {
    // @todo: implemented in per-area PR for PTS-1.4
    await Promise.resolve();
  },
);
Then('the workspace tab navigation bar shows all 7 tabs', async () => {
  // @todo: implemented in per-area PR for PTS-1.4
  await Promise.resolve();
});
Then(
  'the Overview tab metric cards, current job card, repository info, and recent activity panels are populated',
  async () => {
    // @todo: implemented in per-area PR for PTS-1.4
    await Promise.resolve();
  },
);
Then(
  'the TopBar global search placeholder changes to {string}',
  async ({}, _placeholder: string) => {
    // @todo: implemented in per-area PR for PTS-1.4
    await Promise.resolve();
  },
);

// PTS-1.5
When(
  'I type {string} into the TopBar global search',
  async ({}, _query: string) => {
    // @todo: implemented in per-area PR for PTS-1.5
    await Promise.resolve();
  },
);
Then('a debounced search across repositories is triggered', async () => {
  // @todo: implemented in per-area PR for PTS-1.5
  await Promise.resolve();
});
Then('a results dropdown appears below the search bar', async () => {
  // @todo: implemented in per-area PR for PTS-1.5
  await Promise.resolve();
});
Then(
  'the dropdown shows matching documentation entries or a {string} message',
  async ({}, _empty: string) => {
    // @todo: implemented in per-area PR for PTS-1.5
    await Promise.resolve();
  },
);
Then('the search field still displays {string}', async ({}, _query: string) => {
  // @todo: implemented in per-area PR for PTS-1.5
  await Promise.resolve();
});

// PTS-1.6
When('I click the sidebar {string} link', async ({}, _label: string) => {
  // @todo: implemented in per-area PR for PTS-1.6 — opt-in to asDeveloper fixture
  // (see @as-developer tag) once the role-aware tag→fixture toggle is wired.
  await Promise.resolve();
});
Then('the URL changes to {string}', async ({}, _url: string) => {
  // @todo: implemented in per-area PR for PTS-1.6
  await Promise.resolve();
});
Then('the System Health page content is displayed', async () => {
  // @todo: implemented in per-area PR for PTS-1.6
  await Promise.resolve();
});
Then('the All Jobs page content is displayed', async () => {
  // @todo: implemented in per-area PR for PTS-1.6
  await Promise.resolve();
});
Then('the full repository list page is restored', async () => {
  // @todo: implemented in per-area PR for PTS-1.6
  await Promise.resolve();
});
Then('the sidebar System Health link is marked active', async () => {
  // @todo: implemented in per-area PR for PTS-1.6
  await Promise.resolve();
});
Then('the sidebar All Jobs link is marked active', async () => {
  // @todo: implemented in per-area PR for PTS-1.6
  await Promise.resolve();
});
