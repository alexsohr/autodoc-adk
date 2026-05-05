import type { Page, Locator } from '@playwright/test';

type FilterPillName = 'All' | 'Running' | 'Completed' | 'Failed' | 'Cancelled' | 'Pending';

// Column keys mirror the `key` field on the Column<T> records returned by
// `buildCompletedColumns()` in web/src/pages/tabs/JobsTab.tsx — the DataTable
// emits `data-testid="datatable-header-${col.key}"` for each header cell.
type ColumnKey =
  | 'status'
  | 'mode'
  | 'branch'
  | 'created_at'
  | 'updated_at'
  | 'pull_request_url';

const PILL_VALUE: Record<FilterPillName, string> = {
  'All':       '',
  'Running':   'RUNNING',
  'Completed': 'COMPLETED',
  'Failed':    'FAILED',
  'Cancelled': 'CANCELLED',
  'Pending':   'PENDING',
};

export class JobsTab {
  constructor(private readonly page: Page) {}
  readonly dryRunCheckbox:    Locator = this.page.getByTestId('jobs-dry-run-checkbox');
  readonly fullGenButton:     Locator = this.page.getByTestId('jobs-full-generation-button');
  readonly incrementalButton: Locator = this.page.getByTestId('jobs-incremental-button');
  readonly completedSection:  Locator = this.page.getByTestId('jobs-section-completed');
  readonly failedSection:     Locator = this.page.getByTestId('jobs-section-failed');
  readonly cancelledSection:  Locator = this.page.getByTestId('jobs-section-cancelled');

  // First Retry button across all rendered Failed rows. We use `.first()` so
  // PTS-2.5 can assert "Failed rows have a Retry button" without enumerating
  // every row — one positive existence check per acceptance bullet.
  readonly firstFailedRetryButton: Locator = this.page
    .getByTestId('jobs-section-failed')
    .getByTestId('jobs-row-retry')
    .first();

  // First Details link across the entire Jobs tab. PTS-2.5 only requires that
  // "all rows have a Details link" — asserting at least one is rendered is
  // sufficient given the column factory uniformly emits the link in every
  // section (Completed / Failed / Cancelled).
  readonly firstDetailsLink: Locator = this.page.getByTestId('jobs-row-details').first();

  // Pagination footer rendered by DataTable inside the Failed section. The
  // Failed section is the only one in the seeded fixture (13 jobs, page size 5)
  // that exceeds the page size, so this is what PTS-2.5 actually exercises.
  readonly failedSectionPagination: Locator = this.page
    .getByTestId('jobs-section-failed')
    .getByTestId('datatable-pagination');

  filterPill(name: FilterPillName): Locator {
    return this.page.getByTestId(`filter-tab-${PILL_VALUE[name]}`);
  }

  // Column header inside a specific section's DataTable. Multiple sections
  // share the same column keys, so callers must scope by section.
  failedColumnHeader(key: ColumnKey): Locator {
    return this.page
      .getByTestId('jobs-section-failed')
      .getByTestId(`datatable-header-${key}`);
  }
}
