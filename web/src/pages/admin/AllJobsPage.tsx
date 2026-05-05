import { type ReactNode, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  DataTable,
  StatusBadge,
  FilterBar,
  SectionErrorBoundary,
} from "@/components/shared";
import { useAllJobs } from "@/api/hooks";
import { formatRelativeTime } from "@/utils/formatters";
import type { Job } from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type JobRow = Record<string, unknown> & Job;

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AllJobsPage(): ReactNode {
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  const { data: jobs, isLoading, isError, error, refetch } = useAllJobs({ status: statusFilter === "all" ? undefined : statusFilter.toUpperCase() });

  // Status counts (API returns uppercase status values)
  const statusCounts = useMemo(() => {
    const allJobs = jobs ?? [];
    return {
      all: allJobs.length,
      running: allJobs.filter((j) => j.status === "RUNNING").length,
      completed: allJobs.filter((j) => j.status === "COMPLETED").length,
      failed: allJobs.filter((j) => j.status === "FAILED").length,
      pending: allJobs.filter((j) => j.status === "PENDING").length,
      cancelled: allJobs.filter((j) => j.status === "CANCELLED").length,
    };
  }, [jobs]);

  const filterOptions = useMemo(
    () => [
      { label: "All", value: "all", count: statusCounts.all },
      { label: "Running", value: "running", count: statusCounts.running },
      { label: "Completed", value: "completed", count: statusCounts.completed },
      { label: "Failed", value: "failed", count: statusCounts.failed },
      { label: "Pending", value: "pending", count: statusCounts.pending },
    ],
    [statusCounts],
  );

  // Filter and search (API returns uppercase status values)
  const filteredJobs: JobRow[] = useMemo(() => {
    let result = (jobs ?? []) as JobRow[];
    if (statusFilter !== "all") {
      const upperFilter = statusFilter.toUpperCase();
      result = result.filter((j) => j.status === upperFilter);
    }
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter(
        (j) =>
          j.repository_id?.toLowerCase().includes(term) ||
          j.branch?.toLowerCase().includes(term) ||
          j.id?.toLowerCase().includes(term),
      );
    }
    return result;
  }, [jobs, statusFilter, searchTerm]);

  // Stage derivation helper (API returns uppercase status values)
  const getStage = (job: Job): string => {
    if (job.status === "PENDING") return "Queued";
    if (job.status === "CANCELLED") return "Cancelled";
    if (job.status === "FAILED") return "Failed";
    if (job.status === "COMPLETED") return "Done";
    // Running
    return "Running";
  };

  const columns = useMemo(
    () => [
      {
        key: "repository_id",
        header: "Repository",
        sortable: true,
        render: (row: JobRow) => (
          <Link
            to={`/repos/${row.repository_id}`}
            style={{
              color: "var(--autodoc-primary)",
              textDecoration: "none",
              fontWeight: 500,
            }}
          >
            {row.repository_id.slice(0, 8)}...
          </Link>
        ),
      },
      {
        key: "mode",
        header: "Mode",
        sortable: true,
        render: (row: JobRow) => (
          <span
            style={{
              textTransform: "capitalize",
              fontWeight: 500,
            }}
          >
            {row.mode}
          </span>
        ),
      },
      { key: "branch", header: "Branch", sortable: true },
      {
        key: "status",
        header: "Status",
        sortable: true,
        render: (row: JobRow) => <StatusBadge status={row.status?.toLowerCase() as "pending" | "running" | "completed" | "failed" | "cancelled"} />,
      },
      {
        key: "stage",
        header: "Stage",
        render: (row: JobRow) => (
          <span style={{ color: "var(--autodoc-on-surface-variant)", fontSize: "0.8125rem" }}>
            {getStage(row)}
          </span>
        ),
      },
      {
        key: "updated_at",
        header: "Updated",
        sortable: true,
        render: (row: JobRow) => (
          <span style={{ color: "var(--autodoc-on-surface-variant)" }}>
            {row.updated_at ? formatRelativeTime(row.updated_at) : "\u2014"}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "Created",
        sortable: true,
        render: (row: JobRow) => (
          <span style={{ color: "var(--autodoc-on-surface-variant)" }}>
            {formatRelativeTime(row.created_at)}
          </span>
        ),
      },
    ],
    [],
  );

  const expandableRow = (row: JobRow): ReactNode => (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
        gap: "1rem",
        padding: "0.5rem 0",
      }}
    >
      <div>
        <span style={{ fontSize: "0.75rem", color: "var(--autodoc-on-surface-variant)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Job ID
        </span>
        <p style={{ margin: "0.25rem 0 0", fontSize: "0.8125rem", fontFamily: "monospace" }}>{row.id}</p>
      </div>
      <div>
        <span style={{ fontSize: "0.75rem", color: "var(--autodoc-on-surface-variant)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Commit
        </span>
        <p style={{ margin: "0.25rem 0 0", fontSize: "0.8125rem", fontFamily: "monospace" }}>{row.commit_sha?.slice(0, 12) ?? "\u2014"}</p>
      </div>
      <div>
        <span style={{ fontSize: "0.75rem", color: "var(--autodoc-on-surface-variant)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Mode
        </span>
        <p style={{ margin: "0.25rem 0 0", fontSize: "0.8125rem", textTransform: "capitalize" }}>{row.mode ?? "\u2014"}</p>
      </div>
      <div>
        <span style={{ fontSize: "0.75rem", color: "var(--autodoc-on-surface-variant)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Updated
        </span>
        <p style={{ margin: "0.25rem 0 0", fontSize: "0.8125rem" }}>{row.updated_at ? formatRelativeTime(row.updated_at) : "\u2014"}</p>
      </div>
      {row.error_message && (
        <div style={{ gridColumn: "1 / -1" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--autodoc-error)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Error
          </span>
          <p
            style={{
              margin: "0.25rem 0 0",
              fontSize: "0.8125rem",
              color: "var(--autodoc-on-error-container)",
              background: "var(--autodoc-error-container)",
              borderRadius: "8px",
              padding: "0.5rem 0.75rem",
            }}
          >
            {row.error_message}
          </p>
        </div>
      )}
      {row.pull_request_url && (
        <div>
          <span style={{ fontSize: "0.75rem", color: "var(--autodoc-on-surface-variant)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Pull Request
          </span>
          <p style={{ margin: "0.25rem 0 0" }}>
            <a
              href={row.pull_request_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "var(--autodoc-primary)", fontSize: "0.8125rem" }}
            >
              View PR
            </a>
          </p>
        </div>
      )}
    </div>
  );

  return (
    <div className="autodoc-page-padding" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div>
        <h1 className="autodoc-headline-lg" style={{ marginBottom: "0.25rem" }}>
          All Jobs
        </h1>
        <p style={{ color: "var(--autodoc-on-surface-variant)", fontSize: "0.9375rem" }}>
          Cross-repository job monitoring and management
        </p>
      </div>

      {/* Filters + search */}
      <div
        style={{
          display: "flex",
          gap: "1rem",
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <FilterBar options={filterOptions} value={statusFilter} onChange={setStatusFilter} />
        <div style={{ flex: 1, minWidth: "200px" }}>
          <input
            data-testid="all-jobs-search"
            type="text"
            placeholder="Search by repository, branch, or job ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: "100%",
              padding: "0.5rem 0.75rem",
              borderRadius: "8px",
              border: "none",
              background: "var(--autodoc-surface-container-high)",
              color: "var(--autodoc-on-surface)",
              fontSize: "0.8125rem",
              fontFamily: "inherit",
              outline: "none",
              transition: "background-color 200ms ease-out",
            }}
          />
        </div>
      </div>

      {/* Table */}
      <SectionErrorBoundary
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
        data={jobs}
        onRetry={() => void refetch()}
        emptyMessage="No jobs found. Trigger a documentation generation to get started."
      >
        <div data-testid="all-jobs-table">
          <DataTable<JobRow>
            columns={columns}
            data={filteredJobs}
            pageSize={15}
            expandableRow={expandableRow}
            emptyMessage="No jobs match your filters."
          />
        </div>
      </SectionErrorBoundary>
    </div>
  );
}
