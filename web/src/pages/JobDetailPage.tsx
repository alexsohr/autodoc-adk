import {
  type ReactNode,
  useState,
  useEffect,
  useRef,
  useMemo,
} from "react";
import { useParams, Link } from "react-router-dom";
import {
  useJob,
  useJobProgress,
  useJobTasks,
  useJobLogs,
  useCancelJob,
  useRetryJob,
} from "@/api/hooks";
import {
  StatusBadge,
  PipelineVisualization,
  ConfirmDialog,
  SectionErrorBoundary,
} from "@/components/shared";
import { RoleGate } from "@/contexts/AuthContext";
import {
  formatRelativeTime,
  formatDuration,
} from "@/utils/formatters";
import type { Job, JobLog, JobTask } from "@/types";

// ---------------------------------------------------------------------------
// Log level colors
// ---------------------------------------------------------------------------

const LOG_LEVEL_COLOR: Record<string, string> = {
  info: "var(--autodoc-info)",
  warning: "var(--autodoc-warning)",
  error: "var(--autodoc-error)",
  debug: "var(--autodoc-outline)",
};

// ---------------------------------------------------------------------------
// LogViewer
// ---------------------------------------------------------------------------

function LogViewer({ logs }: { logs: JobLog[] }): ReactNode {
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  };

  if (logs.length === 0) {
    return (
      <div
        style={{
          padding: "2rem",
          textAlign: "center",
          color: "var(--autodoc-on-surface-variant)",
          fontSize: "0.875rem",
        }}
      >
        No logs available yet.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      style={{
        background: "var(--autodoc-inverse-surface)",
        borderRadius: "12px",
        padding: "1rem 1.25rem",
        maxHeight: "400px",
        overflow: "auto",
        fontFamily: "monospace",
        fontSize: "0.8125rem",
        lineHeight: 1.75,
      }}
    >
      {logs.map((log, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            gap: "0.75rem",
            color: "var(--autodoc-inverse-on-surface)",
          }}
        >
          <span style={{ color: "var(--autodoc-outline-variant)", flexShrink: 0 }}>
            {new Date(log.timestamp).toLocaleTimeString()}
          </span>
          <span
            style={{
              color: LOG_LEVEL_COLOR[log.level] ?? "var(--autodoc-outline)",
              fontWeight: 600,
              width: "50px",
              flexShrink: 0,
              textTransform: "uppercase",
              fontSize: "0.6875rem",
              letterSpacing: "0.05em",
              lineHeight: "inherit",
              display: "flex",
              alignItems: "center",
            }}
          >
            {log.level}
          </span>
          {log.task && (
            <span
              style={{
                color: "var(--autodoc-primary-fixed-dim)",
                flexShrink: 0,
              }}
            >
              [{log.task}]
            </span>
          )}
          <span style={{ wordBreak: "break-word" }}>{log.message}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TasksTable
// ---------------------------------------------------------------------------

const TASK_STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  completed: {
    bg: "var(--autodoc-success-bg)",
    color: "var(--autodoc-success)",
  },
  running: {
    bg: "var(--autodoc-info-bg)",
    color: "var(--autodoc-info)",
  },
  pending: {
    bg: "var(--autodoc-surface-container-high)",
    color: "var(--autodoc-on-surface-variant)",
  },
  failed: {
    bg: "var(--autodoc-error-container)",
    color: "var(--autodoc-on-error-container)",
  },
};

function TasksTable({ tasks }: { tasks: JobTask[] }): ReactNode {
  if (tasks.length === 0) {
    return (
      <div
        style={{
          padding: "2rem",
          textAlign: "center",
          color: "var(--autodoc-on-surface-variant)",
          fontSize: "0.875rem",
        }}
      >
        No task information available.
      </div>
    );
  }

  return (
    <div
      style={{
        background: "var(--autodoc-surface-container-lowest)",
        borderRadius: "12px",
        overflow: "hidden",
        boxShadow: "var(--autodoc-shadow-ambient)",
      }}
    >
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontFamily: "inherit",
        }}
      >
        <thead>
          <tr style={{ background: "var(--autodoc-surface-container)" }}>
            <th
              style={{
                padding: "0.625rem 1rem",
                textAlign: "left",
                fontSize: "0.75rem",
                fontWeight: 500,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                color: "var(--autodoc-on-surface-variant)",
                border: "none",
              }}
            >
              Task
            </th>
            <th
              style={{
                padding: "0.625rem 1rem",
                textAlign: "left",
                fontSize: "0.75rem",
                fontWeight: 500,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                color: "var(--autodoc-on-surface-variant)",
                border: "none",
                width: "100px",
              }}
            >
              Status
            </th>
            <th
              style={{
                padding: "0.625rem 1rem",
                textAlign: "left",
                fontSize: "0.75rem",
                fontWeight: 500,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                color: "var(--autodoc-on-surface-variant)",
                border: "none",
                width: "100px",
              }}
            >
              Duration
            </th>
            <th
              style={{
                padding: "0.625rem 1rem",
                textAlign: "left",
                fontSize: "0.75rem",
                fontWeight: 500,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                color: "var(--autodoc-on-surface-variant)",
                border: "none",
              }}
            >
              Error
            </th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task, i) => {
            const fallback = { bg: "var(--autodoc-surface-container-high)", color: "var(--autodoc-on-surface-variant)" };
            const resolvedStyle = TASK_STATUS_STYLE[task.status] ?? fallback;
            return (
              <tr
                key={task.name}
                style={{
                  background:
                    i % 2 === 0
                      ? "var(--autodoc-surface-container-lowest)"
                      : "var(--autodoc-surface-container-low)",
                  transition: "background-color 200ms ease-out",
                }}
              >
                <td
                  style={{
                    padding: "0.625rem 1rem",
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    color: "var(--autodoc-on-surface)",
                    border: "none",
                  }}
                >
                  {task.name}
                </td>
                <td style={{ padding: "0.625rem 1rem", border: "none" }}>
                  <span
                    className="autodoc-badge"
                    style={{
                      background: resolvedStyle.bg,
                      color: resolvedStyle.color,
                    }}
                  >
                    {task.status}
                  </span>
                </td>
                <td
                  style={{
                    padding: "0.625rem 1rem",
                    fontSize: "0.8125rem",
                    color: "var(--autodoc-on-surface-variant)",
                    border: "none",
                  }}
                >
                  {formatDuration(task.duration_seconds ?? null)}
                </td>
                <td
                  style={{
                    padding: "0.625rem 1rem",
                    fontSize: "0.8125rem",
                    color: task.error
                      ? "var(--autodoc-error)"
                      : "var(--autodoc-outline)",
                    border: "none",
                    fontFamily: task.error ? "monospace" : "inherit",
                    wordBreak: "break-word",
                  }}
                >
                  {task.error ?? "\u2014"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MetaGrid — key-value metadata
// ---------------------------------------------------------------------------

function MetaGrid({ job }: { job: Job }): ReactNode {
  const items: { label: string; value: ReactNode }[] = [
    { label: "Status", value: <StatusBadge status={job.status?.toLowerCase() as "pending" | "running" | "completed" | "failed" | "cancelled"} /> },
    {
      label: "Mode",
      value: job.mode === "full" ? "Full Generation" : "Incremental Update",
    },
    { label: "Branch", value: job.branch },
    {
      label: "Commit",
      value: (
        <span style={{ fontFamily: "monospace", fontSize: "0.8125rem" }}>
          {job.commit_sha?.slice(0, 12) ?? "\u2014"}
        </span>
      ),
    },
    { label: "Created", value: formatRelativeTime(job.created_at) },
    {
      label: "Updated",
      value: job.updated_at ? formatRelativeTime(job.updated_at) : "\u2014",
    },
  ];

  if (job.pull_request_url) {
    items.push({
      label: "Pull Request",
      value: (
        <a
          href={job.pull_request_url}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            color: "var(--autodoc-primary)",
            fontWeight: 600,
            textDecoration: "none",
          }}
        >
          View PR
        </a>
      ),
    });
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
        gap: "1rem",
        background: "var(--autodoc-surface-container-low)",
        borderRadius: "12px",
        padding: "1.25rem",
      }}
    >
      {items.map((item) => (
        <div key={item.label} style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span
            className="autodoc-label-md"
            style={{ color: "var(--autodoc-outline)" }}
          >
            {item.label}
          </span>
          <span
            style={{
              fontSize: "0.9375rem",
              fontWeight: 500,
              color: "var(--autodoc-on-surface)",
            }}
          >
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// JobDetailPage (default export)
// ---------------------------------------------------------------------------

export default function JobDetailPage(): ReactNode {
  const { id: repoId = "", jobId = "" } = useParams<{
    id: string;
    jobId: string;
  }>();

  const {
    data: job,
    isLoading: jobLoading,
    isError: jobError,
    error: jobErr,
    refetch: refetchJob,
  } = useJob(jobId);

  const isRunning = job?.status === "RUNNING" || job?.status === "PENDING";

  const { data: progress } = useJobProgress(jobId, isRunning);
  const { data: tasks, isLoading: tasksLoading } = useJobTasks(jobId);
  const { data: logs, isLoading: logsLoading } = useJobLogs(jobId);

  const cancelJob = useCancelJob();
  const retryJob = useRetryJob();
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const pipelineStages = useMemo(() => {
    if (progress?.stages) {
      return progress.stages.map((s) => ({
        name: s.name,
        status: s.status,
        duration: s.duration_seconds,
      }));
    }
    return [];
  }, [progress]);

  return (
    <div className="autodoc-page-padding">
      <SectionErrorBoundary
        isLoading={jobLoading}
        isError={jobError}
        error={jobErr instanceof Error ? jobErr : null}
        data={job}
        emptyMessage="Job not found."
        onRetry={() => void refetchJob()}
      >
        {job && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "2rem",
            }}
          >
            {/* Breadcrumb back link + title */}
            <div>
              <Link
                to={`/repos/${repoId}/jobs`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.25rem",
                  fontSize: "0.8125rem",
                  fontWeight: 500,
                  color: "var(--autodoc-primary)",
                  textDecoration: "none",
                  marginBottom: "0.75rem",
                  transition: "opacity 200ms ease-out",
                }}
              >
                <span
                  style={{
                    fontFamily: "'Material Symbols Outlined'",
                    fontSize: "18px",
                    fontVariationSettings: "'FILL' 0, 'wght' 400",
                  }}
                >
                  arrow_back
                </span>
                Back to Jobs
              </Link>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "1rem",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.75rem",
                  }}
                >
                  <h2
                    style={{
                      fontSize: "1.75rem",
                      fontWeight: 700,
                      color: "var(--autodoc-on-surface)",
                      margin: 0,
                    }}
                  >
                    {job.mode === "full"
                      ? "Full Generation"
                      : "Incremental Update"}
                  </h2>
                  <StatusBadge status={job.status} />
                </div>

                {/* Actions */}
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {isRunning && (
                    <RoleGate roles={["developer", "admin"]}>
                      <button
                        onClick={() => setShowCancelConfirm(true)}
                        style={{
                          padding: "0.5rem 1.25rem",
                          borderRadius: "10px",
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
                        Cancel Job
                      </button>
                    </RoleGate>
                  )}
                  {job.status === "FAILED" && (
                    <RoleGate roles={["developer", "admin"]}>
                      <button
                        onClick={() =>
                          retryJob.mutate(job.id, {
                            onSuccess: () => void refetchJob(),
                          })
                        }
                        disabled={retryJob.isPending}
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
                          transition: "opacity 200ms ease-out",
                        }}
                      >
                        Retry
                      </button>
                    </RoleGate>
                  )}
                </div>
              </div>
            </div>

            {/* Error display for failed jobs */}
            {job.status === "FAILED" && job.error_message && (
              <div
                style={{
                  background: "var(--autodoc-error-container)",
                  borderRadius: "12px",
                  padding: "1.25rem 1.5rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                }}
              >
                <span
                  className="autodoc-label-md"
                  style={{ color: "var(--autodoc-on-error-container)" }}
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
                  {job.error_message}
                </pre>
              </div>
            )}

            {/* Metadata grid */}
            <MetaGrid job={job} />

            {/* Pipeline visualization */}
            {pipelineStages.length > 0 && (
              <section>
                <h3
                  className="autodoc-label-md"
                  style={{
                    color: "var(--autodoc-on-surface-variant)",
                    marginBottom: "0.75rem",
                  }}
                >
                  Pipeline
                </h3>
                <div
                  style={{
                    background: "var(--autodoc-surface-container-lowest)",
                    borderRadius: "12px",
                    padding: "1.5rem",
                    boxShadow: "var(--autodoc-shadow-ambient)",
                  }}
                >
                  <PipelineVisualization stages={pipelineStages} />
                </div>
              </section>
            )}

            {/* Scope progress (running only) */}
            {isRunning && progress?.scope_progress && progress.scope_progress.length > 0 && (
              <section>
                <h3
                  className="autodoc-label-md"
                  style={{
                    color: "var(--autodoc-on-surface-variant)",
                    marginBottom: "0.75rem",
                  }}
                >
                  Scope Progress
                </h3>
                <div
                  style={{
                    background: "var(--autodoc-surface-container-low)",
                    borderRadius: "12px",
                    padding: "1rem 1.25rem",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.75rem",
                  }}
                >
                  {progress.scope_progress.map((sp) => {
                    const pct =
                      sp.pages_total > 0
                        ? Math.round(
                            (sp.pages_completed / sp.pages_total) * 100,
                          )
                        : 0;
                    return (
                      <div key={sp.scope_path}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: "0.8125rem",
                            color: "var(--autodoc-on-surface-variant)",
                            marginBottom: "0.25rem",
                          }}
                        >
                          <span style={{ fontWeight: 500 }}>{sp.scope_path}</span>
                          <span>
                            {sp.pages_completed}/{sp.pages_total} ({pct}%)
                          </span>
                        </div>
                        <div
                          style={{
                            height: "8px",
                            borderRadius: "4px",
                            background: "var(--autodoc-surface-container-high)",
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              height: "100%",
                              width: `${pct}%`,
                              borderRadius: "4px",
                              background: "var(--autodoc-info)",
                              transition: "width 400ms ease-out",
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Task states table */}
            <section>
              <h3
                className="autodoc-label-md"
                style={{
                  color: "var(--autodoc-on-surface-variant)",
                  marginBottom: "0.75rem",
                }}
              >
                Tasks
              </h3>
              <SectionErrorBoundary
                isLoading={tasksLoading}
                isError={false}
                data={tasks}
                emptyMessage="No task data available."
              >
                {tasks && <TasksTable tasks={tasks} />}
              </SectionErrorBoundary>
            </section>

            {/* Log viewer */}
            <section>
              <h3
                className="autodoc-label-md"
                style={{
                  color: "var(--autodoc-on-surface-variant)",
                  marginBottom: "0.75rem",
                }}
              >
                Logs
              </h3>
              <SectionErrorBoundary
                isLoading={logsLoading}
                isError={false}
                data={logs}
                emptyMessage="No logs available."
              >
                {logs && <LogViewer logs={logs} />}
              </SectionErrorBoundary>
            </section>
          </div>
        )}
      </SectionErrorBoundary>

      <ConfirmDialog
        open={showCancelConfirm}
        title="Cancel Job"
        message="Are you sure you want to cancel this job? This action cannot be undone."
        confirmLabel="Cancel Job"
        onConfirm={() => {
          setShowCancelConfirm(false);
          cancelJob.mutate(jobId, { onSuccess: () => void refetchJob() });
        }}
        onCancel={() => setShowCancelConfirm(false)}
      />
    </div>
  );
}
