import { test, expect } from '../fixtures/test';
import { WorkspacePage } from '../pages/WorkspacePage';
import { SearchTab } from '../pages/SearchTab';
import { REPOS } from '../helpers/seed-data';

// Source: docs/ui/03-repo-workspace-docs-search-chat.md
// Scenarios: docs/ui/test-scenarios/03-docs-search-chat.test-scenarios.md

test.describe('03 — Repo Workspace · Docs / Search / Chat', () => {

  // PTS-2.4 chosen as the worked example (search UI mechanics work without
  // generated wiki content; PTS-2.3 needs real docs).
  test('PTS-2.4: search tab UI mechanics', async ({ page }) => {
    const ws = new WorkspacePage(page);
    await ws.goto(REPOS.digitalClock.id);
    await ws.tab('Search').click();

    const search = new SearchTab(page);
    await expect(search.input).toBeVisible();
    await expect(search.searchButton).toBeDisabled();
    for (const mode of ['Hybrid', 'Semantic', 'Full Text'] as const) {
      await expect(search.modeButton(mode)).toBeVisible();
    }

    await search.input.fill('tkinter window');
    await expect(search.searchButton).toBeEnabled();
    await search.searchButton.click();
    await expect(page).toHaveURL(/\/search\?q=tkinter\+window/);
  });

  test.skip('PTS-2.3: docs tab with real content', async ({ page }) => {
    // Acceptance: scope selector populated; doc tree renders; first page auto-loads;
    // breadcrumb path + quality pill + importance badge + GFM markdown + Mermaid all render.
  });
});
