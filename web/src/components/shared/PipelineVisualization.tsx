import type { ReactNode } from "react";
import { formatDuration } from "@/utils/formatters";

interface PipelineStage {
  name: string;
  status: "completed" | "active" | "pending" | "failed";
  duration?: number;
}

interface PipelineVisualizationProps {
  stages: PipelineStage[];
}

const STAGE_COLORS: Record<PipelineStage["status"], string> = {
  completed: "var(--autodoc-success)",
  active: "var(--autodoc-info)",
  pending: "var(--autodoc-outline-variant)",
  failed: "var(--autodoc-error)",
};

const STAGE_BG: Record<PipelineStage["status"], string> = {
  completed: "var(--autodoc-success-bg)",
  active: "var(--autodoc-info-bg)",
  pending: "var(--autodoc-surface-container-high)",
  failed: "var(--autodoc-error-container)",
};

export function PipelineVisualization({ stages }: PipelineVisualizationProps): ReactNode {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 0, width: "100%" }}>
      {stages.map((stage, index) => (
        <div
          key={stage.name}
          style={{ display: "flex", alignItems: "flex-start", flex: 1 }}
        >
          {/* Stage node + label */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: "80px" }}>
            {/* Circle */}
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "50%",
                backgroundColor: STAGE_BG[stage.status],
                border: `2px solid ${STAGE_COLORS[stage.status]}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                animation: stage.status === "active" ? "autodoc-pulse 2s ease-in-out infinite" : undefined,
                position: "relative",
              }}
            >
              {stage.status === "completed" && (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M2.5 7L5.5 10L11.5 4"
                    stroke={STAGE_COLORS.completed}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
              {stage.status === "failed" && (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M3.5 3.5L10.5 10.5M10.5 3.5L3.5 10.5"
                    stroke={STAGE_COLORS.failed}
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              )}
              {stage.status === "active" && (
                <div
                  style={{
                    width: "10px",
                    height: "10px",
                    borderRadius: "50%",
                    backgroundColor: STAGE_COLORS.active,
                  }}
                />
              )}
            </div>

            {/* Stage name */}
            <span
              style={{
                marginTop: "0.5rem",
                fontSize: "0.75rem",
                fontWeight: 500,
                color: stage.status === "pending"
                  ? "var(--autodoc-on-surface-variant)"
                  : "var(--autodoc-on-surface)",
                textAlign: "center",
                maxWidth: "100px",
                lineHeight: 1.3,
              }}
            >
              {stage.name}
            </span>

            {/* Duration (completed stages only) */}
            {stage.status === "completed" && stage.duration != null && (
              <span
                style={{
                  marginTop: "0.25rem",
                  fontSize: "0.6875rem",
                  color: "var(--autodoc-on-surface-variant)",
                }}
              >
                {formatDuration(stage.duration)}
              </span>
            )}
          </div>

          {/* Connector line */}
          {index < stages.length - 1 && (
            <div
              style={{
                flex: 1,
                height: "2px",
                backgroundColor: stage.status === "completed"
                  ? STAGE_COLORS.completed
                  : "var(--autodoc-outline-variant)",
                alignSelf: "center",
                marginTop: "15px",
                marginLeft: "-8px",
                marginRight: "-8px",
                minWidth: "24px",
              }}
            />
          )}
        </div>
      ))}

      {/* Pulse animation keyframes */}
      <style>{`
        @keyframes autodoc-pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(38, 77, 217, 0.3); }
          50% { box-shadow: 0 0 0 8px rgba(38, 77, 217, 0); }
        }
      `}</style>
    </div>
  );
}
