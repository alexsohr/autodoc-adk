import { type ReactNode, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  MetricCard,
  StatusBadge,
  PipelineVisualization,
  DataTable,
  SectionErrorBoundary,
} from "@/components/shared";
import { useRepoOverview, useJobProgress, useCreateJob } from "@/api/hooks";
import { useRepoContext } from "@/pages/RepoWorkspace";
import type { ScopeSummary, ActivityEvent, ActivityEventType } from "@/types";
import { formatRelativeTime, formatScore } from "@/utils/formatters";

// ---------------------------------------------------------------------------
// LatestJobCard
// ---------------------------------------------------------------------------

interface LatestJobCardProps {
  repoId: string;
  job: {
    id: string;
    status: "pending" | "running" | "completed" | "failed" | "cancelled";
    mode: "full" | "incremental";
    branch: string;
    created_at: string;
    updated_at: string;
  } | null;
}

function LatestJobCard({ repoId, job }: LatestJobCardProps): ReactNode {
  const navigate = useNavigate();
  const createJob = useCreateJob(repoId);

  const isRunning = job?.status === "running" || job?.status === "pending";
  const { data: progress } = useJobProgress(job?.id ?? "", isRunning);

  if (!job) {
    return (
      <div
        style={{
          background: "var(--autodoc-surface-container-lowest)",
          borderRadius: "16px",
          padding: "2rem",
          boxShadow: "var(--autodoc-shadow-ambient)",
          textAlign: "center",
        }}
      >
        <p style={{ color: "var(--autodoc-on-surface-variant)", margin: "0 0 1rem" }}>
          No jobs have been run yet.
        </p>
        <button
          onClick={() => createJob.mutate({ mode: "full" })}
          disabled={createJob.isPending}
          style={{
            background: "var(--autodoc-gradient-cta)",
            color: "var(--autodoc-on-primary)",
            padding: "0.625rem 1.5rem",
            borderRadius: "12px",
            border: "none",
            fontWeight: 600,
            fontSize: "0.875rem",
            cursor: "pointer",
            transition: "transform 200ms ease-out",
          }}
        >
          Run Full Generation
        </button>
      </div>
    );
  }

  const pipelineStages = progress?.stages?.map((s) => ({
    name: s.name,
    status: s.status,
    duration: s.duration_seconds,
  })) ?? [];

  return (
    <div
      style={{
        background: "var(--autodoc-surface-container-low)",
        borderRadius: "16px",
        padding: "1.5rem",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Decorative blur */}
      <div
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          width: "128px",
          height: "128px",
          background: "color-mix(in srgb, var(--autodoc-primary) 5%, transparent)",
          borderRadius: "50%",
          marginRight: "-64px",
          marginTop: "-64px",
          filter: "blur(40px)",
          pointerEvents: "none",
        }}
      />

      {/* Header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem" }}>
        <div>
          <span
            className="autodoc-badge autodoc-badge--info"
            style={{ fontSize: "0.625rem", letterSpacing: "0.05em" }}
          >
            Current Job: {job.id.slice(0, 8).toUpperCase()}
          </span>
          <h3 style={{ fontSize: "1.25rem", fontWeight: 700, margin: "0.5rem 0 0", color: "var(--autodoc-on-surface)" }}>
            {job.mode === "full" ? "Full Repository Documentation Refresh" : "Incremental Update"}
          </h3>
        </div>
        <StatusBadge status={job.status} />
      </div>

      {/* Pipeline visualization */}
      {pipelineStages.length > 0 && (
        <div style={{ margin: "1rem 0 1.25rem" }}>
          <PipelineVisualization stages={pipelineStages} />
        </div>
      )}

      {/* Progress bar for running jobs */}
      {isRunning && progress && (
        <div style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8125rem", marginBottom: "0.375rem" }}>
            <span style={{ color: "var(--autodoc-on-surface-variant)", fontWeight: 500 }}>
              Stage: {progress.stages?.find((s) => s.status === "active")?.name ?? "Processing"}
            </span>
            <span style={{ color: "var(--autodoc-primary)", fontWeight: 600 }}>
              {Math.round(
                ((progress.stages?.filter((s) => s.status === "completed").length ?? 0) /
                  Math.max(1, progress.stages?.length ?? 1)) *
                  100,
              )}%
            </span>
          </div>
          <div
            style={{
              width: "100%",
              height: "8px",
              borderRadius: "9999px",
              background: "var(--autodoc-surface-container-lowest)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${Math.round(
                  ((progress.stages?.filter((s) => s.status === "completed").length ?? 0) /
                    Math.max(1, progress.stages?.length ?? 1)) *
                    100,
                )}%`,
                height: "100%",
                borderRadius: "9999px",
                background: "var(--autodoc-primary)",
                transition: "width 500ms ease-out",
              }}
            />
          </div>
        </div>
      )}

      {/* Metadata row */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "1.5rem",
          fontSize: "0.8125rem",
          color: "var(--autodoc-on-surface-variant)",
          marginBottom: "1.25rem",
        }}
      >
        <span>
          <strong>Branch:</strong> {job.branch}
        </span>
        <span>
          <strong>Started:</strong> {formatRelativeTime(job.created_at)}
        </span>
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", gap: "0.75rem" }}>
        <button
          onClick={() => createJob.mutate({ mode: "full" })}
          disabled={isRunning || createJob.isPending}
          style={{
            background: isRunning ? "var(--autodoc-surface-container-high)" : "var(--autodoc-gradient-cta)",
            color: isRunning ? "var(--autodoc-outline)" : "var(--autodoc-on-primary)",
            padding: "0.5rem 1.25rem",
            borderRadius: "10px",
            border: "none",
            fontWeight: 600,
            fontSize: "0.8125rem",
            cursor: isRunning ? "default" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: "0.375rem",
            transition: "transform 200ms ease-out",
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M8 5v14l11-7z" fill="currentColor" />
          </svg>
          Run Full Generation
        </button>
        <button
          onClick={() => createJob.mutate({ mode: "incremental" })}
          disabled={isRunning || createJob.isPending}
          style={{
            background: "var(--autodoc-surface-container-lowest)",
            color: isRunning ? "var(--autodoc-outline)" : "var(--autodoc-primary)",
            padding: "0.5rem 1.25rem",
            borderRadius: "10px",
            border: "none",
            fontWeight: 600,
            fontSize: "0.8125rem",
            cursor: isRunning ? "default" : "pointer",
            transition: "background-color 200ms ease-out",
          }}
        >
          Incremental Update
        </button>
        {job && (
          <button
            onClick={() => navigate(`jobs/${job.id}`)}
            style={{
              background: "transparent",
              color: "var(--autodoc-primary)",
              padding: "0.5rem 1rem",
              borderRadius: "10px",
              border: "none",
              fontWeight: 500,
              fontSize: "0.8125rem",
              cursor: "pointer",
              marginLeft: "auto",
            }}
          >
            View Job Details
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RepoInfoPanel
// ---------------------------------------------------------------------------

interface RepoInfoPanelProps {
  repoId: string;
  url: string;
  defaultBranch: string;
  provider: "github" | "bitbucket";
  scopeCount: number;
  pageCount: number;
}

function RepoInfoPanel({ url, defaultBranch, provider, scopeCount, pageCount }: RepoInfoPanelProps): ReactNode {
  return (
    <div
      style={{
        background: "var(--autodoc-surface-container-lowest)",
        borderRadius: "16px",
        padding: "1.5rem",
        boxShadow: "var(--autodoc-shadow-ambient)",
      }}
    >
      <h3 style={{ fontSize: "1.125rem", fontWeight: 700, margin: "0 0 1.5rem", color: "var(--autodoc-on-surface)" }}>
        Repository Info
      </h3>

      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        {/* Source */}
        <InfoRow
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          }
          label="Source"
          value={
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: "var(--autodoc-primary)",
                textDecoration: "none",
                fontSize: "0.875rem",
                fontWeight: 600,
              }}
            >
              {url.replace(/^https?:\/\//, "")}
            </a>
          }
        />

        {/* Provider */}
        <InfoRow
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
              <path d="M12 2a14.5 14.5 0 000 20M2 12h20" stroke="currentColor" strokeWidth="2" />
            </svg>
          }
          label="Provider"
          value={provider === "github" ? "GitHub" : "Bitbucket"}
        />

        {/* Main Branch */}
        <InfoRow
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M6 3v12M18 9a3 3 0 100-6 3 3 0 000 6zM6 21a3 3 0 100-6 3 3 0 000 6zM18 9a9 9 0 01-9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          }
          label="Main Branch"
          value={defaultBranch}
        />

        {/* Webhook */}
        <InfoRow
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M17 1l4 4-4 4M3 11V9a4 4 0 014-4h14M7 23l-4-4 4-4M21 13v2a4 4 0 01-4 4H3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          }
          label="Webhook Status"
          value={
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.375rem" }}>
              Active
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: "var(--autodoc-success)",
                }}
              />
            </span>
          }
        />

        {/* Stats */}
        <InfoRow
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2M9 2h6v4H9V2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          }
          label="Stats"
          value={`${pageCount} pages, ${scopeCount} scopes`}
        />
      </div>
    </div>
  );
}

function InfoRow({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }): ReactNode {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
      <div
        style={{
          width: "40px",
          height: "40px",
          borderRadius: "8px",
          background: "var(--autodoc-surface-container)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--autodoc-on-surface-variant)",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div>
        <p className="autodoc-label-md" style={{ color: "var(--autodoc-outline)", margin: 0, fontSize: "0.625rem" }}>
          {label}
        </p>
        <div style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--autodoc-on-surface)" }}>
          {value}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ActivityTimeline
// ---------------------------------------------------------------------------

const EVENT_COLORS: Record<ActivityEventType, { bg: string; fg: string }> = {
  job_completed: { bg: "var(--autodoc-success-bg)", fg: "var(--autodoc-success)" },
  job_started: { bg: "var(--autodoc-info-bg)", fg: "var(--autodoc-info)" },
  job_failed: { bg: "var(--autodoc-error-container)", fg: "var(--autodoc-error)" },
  job_created: { bg: "var(--autodoc-surface-container-high)", fg: "var(--autodoc-on-surface-variant)" },
};

const EVENT_LABELS: Record<ActivityEventType, string> = {
  job_completed: "Job completed",
  job_started: "Job started",
  job_failed: "Job failed",
  job_created: "Job created",
};

function ActivityTimeline({ events }: { events: ActivityEvent[] }): ReactNode {
  if (events.length === 0) {
    return (
      <p style={{ color: "var(--autodoc-on-surface-variant)", fontSize: "0.875rem", textAlign: "center", padding: "1.5rem" }}>
        No recent activity
      </p>
    );
  }

  return (
    <div
      style={{
        background: "var(--autodoc-surface-container-lowest)",
        borderRadius: "16px",
        padding: "1.5rem",
        boxShadow: "var(--autodoc-shadow-ambient)",
      }}
    >
      <h3 style={{ fontSize: "1.125rem", fontWeight: 700, margin: "0 0 1.5rem", color: "var(--autodoc-on-surface)" }}>
        Recent Activity
      </h3>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "1.5rem",
          position: "relative",
          paddingLeft: "2.5rem",
        }}
      >
        {/* Timeline line */}
        <div
          style={{
            position: "absolute",
            left: "15px",
            top: "8px",
            bottom: "8px",
            width: "1px",
            background: "var(--autodoc-surface-container-high)",
          }}
        />

        {events.slice(0, 8).map((event, idx) => {
          const colors = EVENT_COLORS[event.event] ?? EVENT_COLORS.job_created;
          const description = EVENT_LABELS[event.event] ?? event.event;
          return (
            <div key={`${event.job_id}-${event.event}-${idx}`} style={{ position: "relative" }}>
              {/* Timeline dot */}
              <div
                style={{
                  position: "absolute",
                  left: "-2.5rem",
                  top: 0,
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  background: colors.bg,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  zIndex: 1,
                }}
              >
                {event.event === "job_completed" && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M5 13l4 4L19 7" stroke={colors.fg} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
                {event.event === "job_started" && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M23 4v6h-6M1 20v-6h6" stroke={colors.fg} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
                {event.event === "job_failed" && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M18 6L6 18M6 6l12 12" stroke={colors.fg} strokeWidth="2.5" strokeLinecap="round" />
                  </svg>
                )}
                {event.event === "job_created" && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M12 5v14M5 12h14" stroke={colors.fg} strokeWidth="2" strokeLinecap="round" />
                  </svg>
                )}
              </div>

              {/* Content */}
              <div>
                <p style={{ fontSize: "0.875rem", fontWeight: 600, margin: 0, color: "var(--autodoc-on-surface)" }}>
                  {description}
                </p>
                <p style={{ fontSize: "0.75rem", color: "var(--autodoc-on-surface-variant)", margin: "0.125rem 0 0" }}>
                  {formatRelativeTime(event.timestamp)}
                </p>
                {event.branch && (
                  <div
                    style={{
                      marginTop: "0.5rem",
                      padding: "0.5rem 0.75rem",
                      borderRadius: "8px",
                      background: "var(--autodoc-surface-container)",
                      fontSize: "0.75rem",
                      color: "var(--autodoc-on-surface-variant)",
                    }}
                  >
                    {event.mode} on {event.branch}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ScopeBreakdownTable
// ---------------------------------------------------------------------------

function ScopeBreakdownTable({ scopes }: { scopes: ScopeSummary[] }): ReactNode {
  const columns = useMemo(
    () => [
      {
        key: "scope_path",
        header: "Scope Path",
        render: (row: Record<string, unknown>) => (
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ color: "var(--autodoc-on-surface-variant)", flexShrink: 0 }}>
              <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span style={{ fontWeight: 600 }}>{String(row.scope_path)}</span>
          </div>
        ),
      },
      {
        key: "page_count",
        header: "Pages",
        sortable: true,
        width: "100px",
        render: (row: Record<string, unknown>) => (
          <span style={{ fontWeight: 500 }}>{String(row.page_count)} pages</span>
        ),
      },
      {
        key: "avg_quality_score",
        header: "Quality",
        sortable: true,
        width: "120px",
        render: (row: Record<string, unknown>) => {
          const score = row.avg_quality_score as number | null;
          return (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontWeight: 700, fontSize: "0.875rem" }}>{formatScore(score)}</span>
              {score != null && (
                <div style={{ width: "48px", height: "4px", borderRadius: "9999px", background: "var(--autodoc-surface-container-high)", overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${Math.min(100, (score / 10) * 100)}%`,
                      height: "100%",
                      borderRadius: "9999px",
                      background: score >= 8 ? "var(--autodoc-success)" : score >= 7 ? "var(--autodoc-warning)" : "var(--autodoc-error)",
                    }}
                  />
                </div>
              )}
            </div>
          );
        },
      },
      {
        key: "structure_summary",
        header: "Structure",
        render: (row: Record<string, unknown>) => (
          <span style={{ color: "var(--autodoc-on-surface-variant)", fontSize: "0.8125rem" }}>
            {String(row.structure_summary || "\u2014")}
          </span>
        ),
      },
      {
        key: "status",
        header: "Status",
        width: "120px",
        render: (row: Record<string, unknown>) => {
          const status = String(row.status).toLowerCase();
          let bg = "var(--autodoc-surface-container-high)";
          let fg = "var(--autodoc-on-surface-variant)";
          if (status === "complete" || status === "completed") {
            bg = "var(--autodoc-success-bg)";
            fg = "var(--autodoc-success)";
          } else if (status === "in progress" || status === "running" || status === "in_progress") {
            bg = "var(--autodoc-info-bg)";
            fg = "var(--autodoc-info)";
          } else if (status === "failed") {
            bg = "var(--autodoc-error-container)";
            fg = "var(--autodoc-on-error-container)";
          }
          return (
            <span
              style={{
                padding: "0.125rem 0.5rem",
                borderRadius: "4px",
                background: bg,
                color: fg,
                fontSize: "0.625rem",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.03em",
              }}
            >
              {row.status as string}
            </span>
          );
        },
      },
    ],
    [],
  );

  const tableData = scopes as unknown as Record<string, unknown>[];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h3 style={{ fontSize: "1.125rem", fontWeight: 700, margin: 0, color: "var(--autodoc-on-surface)" }}>
          Scope Breakdown
        </h3>
      </div>
      <DataTable columns={columns} data={tableData} pageSize={10} emptyMessage="No scopes configured" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// OverviewTab
// ---------------------------------------------------------------------------

export default function OverviewTab(): ReactNode {
  const { repo, repoId } = useRepoContext();
  const { data: overview, isLoading, isError, error, refetch } = useRepoOverview(repoId);

  return (
    <SectionErrorBoundary
      isLoading={isLoading}
      isError={isError}
      error={error instanceof Error ? error : null}
      data={overview}
      onRetry={() => void refetch()}
      emptyMessage="Overview data is not available yet."
    >
      {overview && (
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
          {/* Top row: 4 metric cards */}
          <SectionErrorBoundary isLoading={false} isError={false} data={overview}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1.5rem" }}>
              <MetricCard
                label="Doc Pages"
                value={overview.page_count.toLocaleString()}
                delta={overview.page_count > 0 ? "+2" : undefined}
                icon="description"
              />
              <MetricCard
                label="Avg Quality"
                value={overview.avg_quality_score != null ? `${formatScore(overview.avg_quality_score)}/10` : "\u2014"}
                subtitle={overview.avg_quality_score != null && overview.avg_quality_score >= 8.0 ? "Excellent" : undefined}
                icon="high_quality"
              />
              <MetricCard
                label="Scopes"
                value={overview.scope_summaries?.length ?? 0}
                subtitle={
                  (overview.scope_summaries?.length ?? 0) > 0
                    ? overview.scope_summaries.map((s) => s.scope_path.split("/").pop()).join(", ")
                    : undefined
                }
                icon="layers"
              />
              <MetricCard
                label="Last Generated"
                value={repo.last_generated_at ? formatRelativeTime(repo.last_generated_at) : "\u2014"}
                subtitle={overview.last_job ? `${overview.last_job.mode} run` : undefined}
                icon="schedule"
              />
            </div>
          </SectionErrorBoundary>

          {/* Two-column layout */}
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "2rem" }}>
            {/* Left column */}
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
              {/* Latest Job */}
              <SectionErrorBoundary isLoading={false} isError={false} data={overview}>
                <LatestJobCard repoId={repoId} job={overview.last_job} />
              </SectionErrorBoundary>

              {/* Scope Breakdown Table */}
              <SectionErrorBoundary isLoading={false} isError={false} data={overview.scope_summaries}>
                <ScopeBreakdownTable scopes={overview.scope_summaries ?? []} />
              </SectionErrorBoundary>
            </div>

            {/* Right column */}
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
              {/* Repo Info */}
              <SectionErrorBoundary isLoading={false} isError={false} data={repo}>
                <RepoInfoPanel
                  repoId={repoId}
                  url={repo.url}
                  defaultBranch={repo.default_branch}
                  provider={repo.provider}
                  scopeCount={repo.scope_count}
                  pageCount={repo.page_count}
                />
              </SectionErrorBoundary>

              {/* Activity Timeline */}
              <SectionErrorBoundary
                isLoading={false}
                isError={false}
                data={(overview.recent_activity?.length ?? 0) > 0 ? overview.recent_activity : undefined}
                emptyMessage="No recent activity"
              >
                <ActivityTimeline events={overview.recent_activity ?? []} />
              </SectionErrorBoundary>
            </div>
          </div>
        </div>
      )}
    </SectionErrorBoundary>
  );
}
