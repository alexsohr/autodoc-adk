import type { Page, Locator } from '@playwright/test';

type ServiceCardName = 'API Cluster' | 'Prefect Server' | 'PostgreSQL' | 'Active Workers';

// Work Pools table column slugs match the React column `key` (DataTable renders
// `data-testid="datatable-header-${col.key}"`). See SystemHealthPage.tsx
// `poolColumns` definition.
type PoolColumnKey = 'name' | 'type' | 'concurrency_limit' | 'status';

// Footer stat tiles. Slugs come from the Gherkin step text mapped 1:1 to the
// `data-testid` suffix on each tile (kebab-case of the label).
type FooterStatSlug = 'last-sync' | 'encrypted' | 'throughput' | 'history';

export class HealthPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/admin/health');
    await this.heading.waitFor();
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Header / hero
  // ───────────────────────────────────────────────────────────────────────────
  readonly heading:  Locator = this.page.getByRole('heading', { name: /Infrastructure Snapshot/i });
  readonly subtitle: Locator = this.page.getByTestId('health-subtitle');

  // ───────────────────────────────────────────────────────────────────────────
  // Service cards (4)
  // ───────────────────────────────────────────────────────────────────────────
  serviceCard(name: ServiceCardName): Locator {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    return this.page.getByTestId(`health-service-card-${slug}`);
  }

  // Each MetricCardWithStatus renders a status badge with class
  // `autodoc-badge--success`. We scope the lookup inside the card so a single
  // step ("the service card 'X' shows a status badge") can assert it.
  serviceCardStatusBadge(name: ServiceCardName): Locator {
    return this.serviceCard(name).locator('.autodoc-badge');
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Work Pools table
  // ───────────────────────────────────────────────────────────────────────────
  readonly workPoolsTable: Locator = this.page.getByTestId('work-pools-table');

  // Column headers are rendered by the shared DataTable component, which sets
  // `data-testid="datatable-header-${col.key}"`. Scope inside `workPoolsTable`
  // so we don't pick up other DataTables on the page.
  workPoolsColumnHeader(key: PoolColumnKey): Locator {
    return this.workPoolsTable.getByTestId(`datatable-header-${key}`);
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Worker Capacity section
  // ───────────────────────────────────────────────────────────────────────────
  readonly workerCapacitySection: Locator = this.page.getByTestId('health-worker-capacity');
  readonly capacityCurrentPeak:   Locator = this.page.getByTestId('health-capacity-current-peak');
  readonly capacityAvgWait:       Locator = this.page.getByTestId('health-capacity-avg-wait');

  // ───────────────────────────────────────────────────────────────────────────
  // Scale On-Demand CTA banner
  // ───────────────────────────────────────────────────────────────────────────
  readonly ctaBanner:        Locator = this.page.getByTestId('health-cta-banner');
  readonly ctaConfigureBtn:  Locator = this.page.getByTestId('health-cta-configure');
  readonly ctaViewLogsBtn:   Locator = this.page.getByTestId('health-cta-view-logs');

  // ───────────────────────────────────────────────────────────────────────────
  // Footer stats grid (4 tiles)
  // ───────────────────────────────────────────────────────────────────────────
  footerStat(slug: FooterStatSlug): Locator {
    return this.page.getByTestId(`health-footer-${slug}`);
  }
}
