import { expect } from '@playwright/test';
import { Given, Then, When } from './bdd';
import { WorkspacePage } from '../pages/WorkspacePage';
import { SearchTab } from '../pages/SearchTab';
import { DocsTab } from '../pages/DocsTab';
import { stubSearch503 } from '../support/api-stubs';

type TabName = 'Overview' | 'Docs' | 'Search' | 'Chat' | 'Jobs' | 'Quality' | 'Settings';
type SearchMode = 'Hybrid' | 'Semantic' | 'Full Text';

// ─────────────────────────────────────────────────────────────────────────────
// PTS-2.4 — Implemented steps (Search tab + 503 fallback)
// ─────────────────────────────────────────────────────────────────────────────

Given('the search documents endpoint returns 503', async ({ page }) => {
  await stubSearch503(page);
});

// Distinct phrasing from workspace.steps.ts's placeholder
// `When I click the workspace {string} tab` (which is a no-op for PTS-2.2).
// We need an actually-implemented action so PTS-2.4 can navigate to /search.
When(
  'I open the workspace {string} tab',
  async ({ page }, name: string) => {
    const ws = new WorkspacePage(page);
    await ws.tab(name as TabName).click();
  },
);

Then(
  'the search input is visible with placeholder {string}',
  async ({ page }, placeholder: string) => {
    const search = new SearchTab(page);
    await expect(search.input).toBeVisible();
    await expect(search.input).toHaveAttribute('placeholder', placeholder);
  },
);

Then(
  'the search mode button {string} is visible',
  async ({ page }, mode: string) => {
    const search = new SearchTab(page);
    await expect(search.modeButton(mode as SearchMode)).toBeVisible();
  },
);

Then('the Search submit button is disabled', async ({ page }) => {
  const search = new SearchTab(page);
  await expect(search.searchButton).toBeDisabled();
});

Then('the Search submit button is enabled', async ({ page }) => {
  const search = new SearchTab(page);
  await expect(search.searchButton).toBeEnabled();
});

When(
  'I type {string} into the search input',
  async ({ page }, query: string) => {
    const search = new SearchTab(page);
    await search.input.fill(query);
  },
);

When('I click the Search submit button', async ({ page }) => {
  const search = new SearchTab(page);
  await search.searchButton.click();
});

Then(
  'the search results area shows a service-unavailable error state',
  async ({ page }) => {
    const search = new SearchTab(page);
    await expect(search.errorState).toBeVisible();
    // The boundary's ErrorPanel renders ApiError.message, which for a 503
    // response from src/api/client.ts is `response.statusText` — i.e. the
    // literal "Service Unavailable" string.
    await expect(search.errorState).toContainText(/Service Unavailable/i);
  },
);

// ─────────────────────────────────────────────────────────────────────────────
// PTS-2.3 — Placeholder steps (Docs tab with real content)
//
// PTS-2.3 is tagged @todo and skipped at runtime by support/hooks.ts.
// playwright-bdd codegen requires every step in every scenario to have a
// definition, even when the scenario will be skipped — so each placeholder
// below resolves immediately. They will be replaced with real implementations
// in the per-scenario PR that removes the @todo tag.
// See features/README.md § Authoring a new feature.
//
// When implementing, point assertions at DocsTab PO locators (scopeSelector,
// docTree, qualityPill, mermaid, prevButton, nextButton). The "treeItem"
// factory currently uses getByRole('treeitem'), which the source does not
// emit — adding `data-testid="docs-tree-item-${page_key}"` to the page Link
// in web/src/pages/tabs/DocsTab.tsx (around line 230) and updating the PO is
// the recommended path; document the slug naming when you do.
// ─────────────────────────────────────────────────────────────────────────────

Then(
  'the docs scope selector shows at least one scope with its page count',
  async () => {
    // @todo: implement when PTS-2.3 is wired up — assert DocsTab.scopeSelector
    //        is visible and contains a "(N pages)" suffix.
    await Promise.resolve();
  },
);

Then(
  'the doc tree renders hierarchical sections with folder and page nodes',
  async () => {
    // @todo: implement when PTS-2.3 is wired up — assert DocsTab.docTree shows
    //        nested folder/page nodes (multi-section structure).
    await Promise.resolve();
  },
);

Then(
  'the doc viewer auto-navigates to the first page in the tree',
  async () => {
    // @todo: implement when PTS-2.3 is wired up — assert URL contains
    //        `/docs/<first-page-slug>` shortly after Docs tab loads.
    await Promise.resolve();
  },
);

Then('the doc viewer breadcrumb path is visible', async () => {
  // @todo: implement when PTS-2.3 is wired up
  await Promise.resolve();
});

Then('the doc viewer quality score pill is visible', async () => {
  // @todo: implement when PTS-2.3 is wired up — DocsTab.qualityPill
  await Promise.resolve();
});

Then('the doc viewer importance badge is visible', async () => {
  // @todo: implement when PTS-2.3 is wired up
  await Promise.resolve();
});

Then(
  'the page viewer renders headings, paragraphs, lists, tables, and code blocks',
  async () => {
    // @todo: implement when PTS-2.3 is wired up — combined GFM markdown
    //        smoke check; split into individual Then steps if any sub-element
    //        starts being asserted on independently.
    await Promise.resolve();
  },
);

Then('the doc viewer renders Mermaid diagrams', async () => {
  // @todo: implement when PTS-2.3 is wired up — DocsTab.mermaid
  await Promise.resolve();
});

Then('the doc viewer shows source file links', async () => {
  // @todo: implement when PTS-2.3 is wired up
  await Promise.resolve();
});

Then(
  'the doc viewer prev and next navigation buttons are present',
  async () => {
    // @todo: implement when PTS-2.3 is wired up — DocsTab.prevButton / nextButton
    await Promise.resolve();
  },
);

When('I click a different page in the doc tree', async () => {
  // @todo: implement when PTS-2.3 is wired up — needs the docs-tree-item
  //        testid hook described above (or a stable role-based locator).
  await Promise.resolve();
});

Then('the doc viewer updates to show that page', async () => {
  // @todo: implement when PTS-2.3 is wired up
  await Promise.resolve();
});
