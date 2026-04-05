import {
  type ReactNode,
  useState,
  useMemo,
  useCallback,
} from "react";
import { useParams, Link } from "react-router-dom";
import {
  useJobs,
  useJobProgress,
  useCreateJob,
  useCancelJob,
  useRetryJob,
} from "@/api/hooks";
import {
  StatusBadge,
  FilterBar,
  PipelineVisualization,
  DataTable,
  ConfirmDialog,
  SectionErrorBoundary,
} from "@/components/shared";
import { RoleGate } from "@/contexts/AuthContext";
import {
  formatRelativeTime,
} from "@/utils/formatters";
import type { Job, JobProgress as JobProgressT, ScopeProgress } from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_FILTERS = [
  { label: "All", value: "" },
  { label: "Running", value: "RUNNING" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Failed", value: "FAILED" },
  { label: "Cancelled", value: "CANCELLED" },
  { label: "Pending", value: "PENDING" },
];

// ---------------------------------------------------------------------------
// RunningJobCard
// ---------------------------------------------------------------------------

function ScopeProgressBar({ scope }: { scope: ScopeProgress }): ReactNode {
  const pct =
    scope.pages_total > 0
      ? Math.round((scope.pages_completed / scope.pages_total) * 100)
      : 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.75rem",
          color: "var(--autodoc-on-surface-variant)",
        }}
      >
        <span style={{ fontWeight: 500 }}>{scope.scope_path}</span>
        <span>
          {scope.pages_completed}/{scope.pages_total}
        </span>
      </div>
      <div
        style={{
          height: "6px",
          borderRadius: "3px",
          background: "var(--autodoc-surface-container-high)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            borderRadius: "3px",
            background: "var(--autodoc-info)",
            transition: "width 400ms ease-out",
          }}
        />
      </div>
    </div>
  );
}

function RunningJobCard({
  job,
  progress,
  onCancel,
}: {
  job: Job;
  progress: JobProgressT | undefined;
  onCancel: (jobId: string) => void;
}): ReactNode {
  const [showConfirm, setShowConfirm] = useState(false);

  return (
    <>
      <div
        style={{
          background: "var(--autodoc-surface-container-lowest)",
          borderRadius: "16px",
          padding: "1.5rem",
          boxShadow: "var(--autodoc-shadow-ambient)",
          borderLeft: "4px solid var(--autodoc-info)",
          display: "flex",
          flexDirection: "column",
          gap: "1.25rem",
        }}
      >
        {/* Header row */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <Link
              to={`jobs/${job.id}`}
              style={{
                fontSize: "1rem",
                fontWeight: 700,
                color: "var(--autodoc-on-surface)",
                textDecoration: "none",
              }}
            >
              {job.mode === "full" ? "Full Generation" : "Incremental Update"}
            </Link>
            <StatusBadge status="running" />
            <span
              style={{
                fontSize: "0.75rem",
                color: "var(--autodoc-outline)",
              }}
            >
              {job.branch} @ {job.commit_sha?.slice(0, 7) ?? ""}
            </span>
          </div>
          <RoleGate roles={["developer", "admin"]}>
            <button
              onClick={() => setShowConfirm(true)}
              style={{
                padding: "0.375rem 1rem",
                borderRadius: "8px",
                border: "none",
                background: "var(--autodoc-error-container)",
                color: "var(--autodoc-on-error-container)",
                fontWeight: 600,
                fontSize: "0.8125rem",
                cursor: "pointer",
                fontFamily: "inherit",
                transition: "opacity 200ms ease-out",
              }}
            >
              Cancel
            </button>
          </RoleGate>
        </div>

        {/* Pipeline */}
        {progress?.stages && (
          <PipelineVisualization
            stages={progress.stages.map((s) => ({
              name: s.name,
              status: s.status,
              duration: s.duration_seconds,
            }))}
          />
        )}

        {/* Scope progress bars */}
        {progress?.scope_progress && progress.scope_progress.length > 0 && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "0.5rem",
              background: "var(--autodoc-surface-container-low)",
              borderRadius: "12px",
              padding: "1rem",
            }}
          >
            {progress.scope_progress.map((sp) => (
              <ScopeProgressBar key={sp.scope_path} scope={sp} />
            ))}
          </div>
        )}

        {/* Started time */}
        <div
          style={{
            fontSize: "0.75rem",
            color: "var(--autodoc-outline)",
          }}
        >
          Started {formatRelativeTime(job.created_at ?? "")}
        </div>
      </div>

      <ConfirmDialog
        open={showConfirm}
        title="Cancel Job"
        message={`Are you sure you want to cancel this ${job.mode} generation job? This cannot be undone.`}
        confirmLabel="Cancel Job"
        onConfirm={() => {
          setShowConfirm(false);
          onCancel(job.id);
        }}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// RunningJobsSection — polls progress for each running job
// ---------------------------------------------------------------------------

function RunningJobWithProgress({
  job,
  onCancel,
}: {
  job: Job;
  onCancel: (jobId: string) => void;
}): ReactNode {
  const { data: progress } = useJobProgress(job.id, true);
  return <RunningJobCard job={job} progress={progress} onCancel={onCancel} />;
}

// ---------------------------------------------------------------------------
// Completed job table columns
// ---------------------------------------------------------------------------

function buildCompletedColumns(_repoId: string) {
  return [
    {
      key: "status",
      header: "Status",
      width: "90px",
      render: (row: Record<string, unknown>) => (
        <StatusBadge status={(row as unknown as Job).status?.toLowerCase() as "pending" | "running" | "completed" | "failed" | "cancelled"} />
      ),
    },
    {
      key: "mode",
      header: "Mode",
      width: "110px",
      render: (row: Record<string, unknown>) => {
        const j = row as unknown as Job;
        return (
          <span style={{ fontWeight: 500, fontSize: "0.875rem" }}>
            {j.mode === "full" ? "Full" : "Incremental"}
          </span>
        );
      },
    },
    {
      key: "branch",
      header: "Branch",
      render: (row: Record<string, unknown>) => {
        const j = row as unknown as Job;
        return (
          <span style={{ fontSize: "0.8125rem" }}>
            {j.branch}{" "}
            <span style={{ color: "var(--autodoc-outline)", fontFamily: "monospace", fontSize: "0.75rem" }}>
              {j.commit_sha?.slice(0, 7) ?? ""}
            </span>
          </span>
        );
      },
    },
    {
      key: "created_at",
      header: "Created",
      width: "100px",
      sortable: true,
      render: (row: Record<string, unknown>) =>
        formatRelativeTime((row as unknown as Job).created_at),
    },
    {
      key: "updated_at",
      header: "Updated",
      width: "100px",
      render: (row: Record<string, unknown>) => {
        const j = row as unknown as Job;
        return j.updated_at ? formatRelativeTime(j.updated_at) : "\u2014";
      },
    },
    {
      key: "pull_request_url",
      header: "PR",
      width: "60px",
      render: (row: Record<string, unknown>) => {
        const j = row as unknown as Job;
        if (!j.pull_request_url) return <span style={{ color: "var(--autodoc-outline)" }}>{"\u2014"}</span>;
        return (
          <a
            href={j.pull_request_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "var(--autodoc-primary)",
              fontWeight: 600,
              fontSize: "0.8125rem",
              textDecoration: "none",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            View
          </a>
        );
      },
    },
    {
      key: "detail",
      header: "",
      width: "60px",
      render: (row: Record<string, unknown>) => {
        const j = row as unknown as Job;
        return (
          <Link
            to={`jobs/${j.id}`}
            style={{
              color: "var(--autodoc-primary)",
              fontWeight: 500,
              fontSize: "0.8125rem",
              textDecoration: "none",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            Details
          </Link>
        );
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Failed job row (inline)
// ---------------------------------------------------------------------------

function FailedJobExpandable(row: Record<string, unknown>): ReactNode {
  const job = row as unknown as Job;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {/* Error box */}
      <div
        style={{
          background: "var(--autodoc-error-container)",
          borderRadius: "10px",
          padding: "1rem 1.25rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
        }}
      >
        <span
          style={{
            fontSize: "0.75rem",
            fontWeight: 600,
            color: "var(--autodoc-on-error-container)",
            letterSpacing: "0.03em",
            textTransform: "uppercase",
          }}
        >
          Error
        </span>
        <pre
          style={{
            margin: 0,
            fontFamily: "monospace",
            fontSize: "0.8125rem",
            lineHeight: 1.6,
            color: "var(--autodoc-on-error-container)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {job.error_message ?? "Unknown error"}
        </pre>
      </div>

      {/* Pipeline visualization if available */}
      <PipelineVisualization
        stages={[
          { name: "Clone", status: "completed" },
          { name: "Structure", status: "completed" },
          { name: "Generate", status: "failed" },
          { name: "Embed", status: "pending" },
          { name: "PR", status: "pending" },
        ]}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Trigger buttons
// ---------------------------------------------------------------------------

function TriggerButtons({
  repoId,
  dryRun,
  onToggleDryRun,
}: {
  repoId: string;
  dryRun: boolean;
  onToggleDryRun: () => void;
}): ReactNode {
  const createJob = useCreateJob(repoId);

  return (
    <RoleGate roles={["developer", "admin"]}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
        }}
      >
        {/* Dry run toggle */}
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            fontSize: "0.8125rem",
            color: "var(--autodoc-on-surface-variant)",
            cursor: "pointer",
            userSelect: "none",
          }}
        >
          <input
            type="checkbox"
            checked={dryRun}
            onChange={onToggleDryRun}
            style={{ accentColor: "var(--autodoc-primary)" }}
          />
          Dry run
        </label>

        <button
          onClick={() => createJob.mutate({ mode: "incremental" })}
          disabled={createJob.isPending}
          style={{
            padding: "0.5rem 1.25rem",
            borderRadius: "10px",
            border: "none",
            background: "var(--autodoc-surface-container)",
            color: "var(--autodoc-primary)",
            fontWeight: 600,
            fontSize: "0.8125rem",
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "background-color 200ms ease-out",
          }}
        >
          Incremental
        </button>

        <button
          onClick={() => createJob.mutate({ mode: "full" })}
          disabled={createJob.isPending}
          style={{
            padding: "0.5rem 1.25rem",
            borderRadius: "10px",
            border: "none",
            background: "var(--autodoc-gradient-cta)",
            color: "var(--autodoc-on-primary)",
            fontWeight: 600,
            fontSize: "0.8125rem",
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "opacity 200ms ease-out, transform 200ms ease-out",
          }}
        >
          Full Generation
        </button>
      </div>
    </RoleGate>
  );
}

// ---------------------------------------------------------------------------
// JobsTab (default export)
// ---------------------------------------------------------------------------

export default function JobsTab(): ReactNode {
  const { id: repoId = "" } = useParams<{ id: string }>();
  const [statusFilter, setStatusFilter] = useState("");
  const [dryRun, setDryRun] = useState(false);

  const {
    data: jobs,
    isLoading,
    isError,
    error,
    refetch,
  } = useJobs(repoId, statusFilter ? { status: statusFilter } : undefined);

  const cancelJob = useCancelJob();
  const retryJob = useRetryJob();

  const handleCancel = useCallback(
    (jobId: string) => {
      cancelJob.mutate(jobId, { onSuccess: () => void refetch() });
    },
    [cancelJob, refetch],
  );

  const handleRetry = useCallback(
    (jobId: string) => {
      retryJob.mutate(jobId, { onSuccess: () => void refetch() });
    },
    [retryJob, refetch],
  );

  // Partition jobs (API returns uppercase status values)
  const runningJobs = useMemo(
    () => (jobs ?? []).filter((j) => j.status === "RUNNING" || j.status === "PENDING"),
    [jobs],
  );
  const completedJobs = useMemo(
    () => (jobs ?? []).filter((j) => j.status === "COMPLETED"),
    [jobs],
  );
  const failedJobs = useMemo(
    () => (jobs ?? []).filter((j) => j.status === "FAILED"),
    [jobs],
  );
  const cancelledJobs = useMemo(
    () => (jobs ?? []).filter((j) => j.status === "CANCELLED"),
    [jobs],
  );

  // Count-enriched filter options
  const filterOptions = useMemo(() => {
    const allJobs = jobs ?? [];
    return STATUS_FILTERS.map((f) => ({
      ...f,
      count: f.value
        ? allJobs.filter((j) => j.status === f.value).length
        : allJobs.length,
    }));
  }, [jobs]);

  // Columns for completed jobs
  const completedColumns = useMemo(() => buildCompletedColumns(repoId), [repoId]);

  // Failed jobs columns — reuse completed but add retry
  const failedColumns = useMemo(() => {
    const cols = buildCompletedColumns(repoId);
    // Replace the last "detail" column with a Retry + Details column
    return cols.map((c) => {
      if (c.key === "detail") {
        return {
          ...c,
          header: "",
          width: "120px",
          render: (row: Record<string, unknown>) => {
            const j = row as unknown as Job;
            return (
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <RoleGate roles={["developer", "admin"]}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRetry(j.id);
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--autodoc-primary)",
                      fontWeight: 600,
                      fontSize: "0.8125rem",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      padding: 0,
                    }}
                  >
                    Retry
                  </button>
                </RoleGate>
                <Link
                  to={`jobs/${j.id}`}
                  style={{
                    color: "var(--autodoc-primary)",
                    fontWeight: 500,
                    fontSize: "0.8125rem",
                    textDecoration: "none",
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  Details
                </Link>
              </div>
            );
          },
        };
      }
      return c;
    });
  }, [repoId, handleRetry]);

  // Cancelled job columns
  const cancelledColumns = useMemo(() => {
    const base = buildCompletedColumns(repoId);
    return base.map((c) => {
      if (c.key === "pull_request_url") return { ...c, header: "Cancelled", width: "110px", render: (row: Record<string, unknown>) => {
        const j = row as unknown as Job;
        return (
          <span style={{ fontSize: "0.8125rem", color: "var(--autodoc-outline)" }}>
            {j.updated_at ? formatRelativeTime(j.updated_at) : "\u2014"}
          </span>
        );
      }};
      return c;
    });
  }, [repoId]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "1.5rem",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <FilterBar
          options={filterOptions}
          value={statusFilter}
          onChange={setStatusFilter}
        />
        <TriggerButtons
          repoId={repoId}
          dryRun={dryRun}
          onToggleDryRun={() => setDryRun((d) => !d)}
        />
      </div>

      {/* Error state */}
      {isError && (
        <div
          style={{
            background: "var(--autodoc-error-container)",
            borderRadius: "12px",
            padding: "1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span
            style={{
              color: "var(--autodoc-on-error-container)",
              fontWeight: 600,
              fontSize: "0.875rem",
            }}
          >
            Failed to load jobs{error instanceof Error ? `: ${error.message}` : ""}
          </span>
          <button
            onClick={() => void refetch()}
            style={{
              padding: "0.375rem 1rem",
              borderRadius: "8px",
              border: "none",
              background: "var(--autodoc-on-error-container)",
              color: "var(--autodoc-error-container)",
              fontWeight: 600,
              fontSize: "0.8125rem",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Retry
          </button>
        </div>
      )}

      <SectionErrorBoundary
        isLoading={isLoading}
        isError={isError}
        error={error instanceof Error ? error : null}
        data={jobs}
        emptyMessage="No jobs found. Trigger a documentation generation to get started."
        onRetry={() => void refetch()}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "2rem",
          }}
        >
          {/* Running / Pending jobs */}
          {runningJobs.length > 0 && (
            <section>
              <h3
                className="autodoc-label-md"
                style={{
                  color: "var(--autodoc-on-surface-variant)",
                  marginBottom: "0.75rem",
                }}
              >
                Active Jobs
              </h3>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem",
                }}
              >
                {runningJobs.map((job) => (
                  <RunningJobWithProgress
                    key={job.id}
                    job={job}
                    onCancel={handleCancel}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Completed jobs */}
          {(statusFilter === "" || statusFilter === "COMPLETED") &&
            completedJobs.length > 0 && (
              <section>
                <h3
                  className="autodoc-label-md"
                  style={{
                    color: "var(--autodoc-on-surface-variant)",
                    marginBottom: "0.75rem",
                  }}
                >
                  Completed
                </h3>
                <DataTable
                  columns={completedColumns}
                  data={completedJobs as unknown as Record<string, unknown>[]}
                  pageSize={10}
                  expandableRow={() => {
                    return (
                      <div style={{ padding: "0.5rem 0" }}>
                        <PipelineVisualization
                          stages={[
                            { name: "Clone", status: "completed", duration: 5 },
                            { name: "Structure", status: "completed", duration: 12 },
                            { name: "Generate", status: "completed" },
                            { name: "Embed", status: "completed", duration: 8 },
                            { name: "PR", status: "completed", duration: 3 },
                          ]}
                        />
                      </div>
                    );
                  }}
                />
              </section>
            )}

          {/* Failed jobs */}
          {(statusFilter === "" || statusFilter === "FAILED") &&
            failedJobs.length > 0 && (
              <section>
                <h3
                  className="autodoc-label-md"
                  style={{
                    color: "var(--autodoc-on-surface-variant)",
                    marginBottom: "0.75rem",
                  }}
                >
                  Failed
                </h3>
                <DataTable
                  columns={failedColumns}
                  data={failedJobs as unknown as Record<string, unknown>[]}
                  pageSize={5}
                  expandableRow={FailedJobExpandable}
                />
              </section>
            )}

          {/* Cancelled jobs */}
          {(statusFilter === "" || statusFilter === "CANCELLED") &&
            cancelledJobs.length > 0 && (
              <section>
                <h3
                  className="autodoc-label-md"
                  style={{
                    color: "var(--autodoc-on-surface-variant)",
                    marginBottom: "0.75rem",
                  }}
                >
                  Cancelled
                </h3>
                <div style={{ opacity: 0.65 }}>
                  <DataTable
                    columns={cancelledColumns}
                    data={cancelledJobs as unknown as Record<string, unknown>[]}
                    pageSize={5}
                  />
                </div>
              </section>
            )}
        </div>
      </SectionErrorBoundary>
    </div>
  );
}
