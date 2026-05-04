import type { Page, Locator } from '@playwright/test';

type AgentName = 'Structure Extractor' | 'Page Generator' | 'README Distiller';

export class QualityTab {
  constructor(private readonly page: Page) {}
  agentCard(name: AgentName): Locator {
    return this.page.getByRole('article').filter({ hasText: name });
  }
  readonly pageQualityTable: Locator = this.page.getByRole('table', { name: /Page Quality|page quality/i });
}
