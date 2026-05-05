import type { Page, Locator } from '@playwright/test';

type AgentName = 'Structure Extractor' | 'Page Generator' | 'README Distiller';

const AGENT_SLUG: Record<AgentName, string> = {
  'Structure Extractor': 'structure-extractor',
  'Page Generator':      'page-generator',
  'README Distiller':    'readme-distiller',
};

export class QualityTab {
  constructor(private readonly page: Page) {}
  agentCard(name: AgentName): Locator {
    return this.page.getByTestId(`quality-agent-card-${AGENT_SLUG[name]}`);
  }
  readonly pageQualityTable: Locator = this.page.getByTestId('quality-page-table');
}
