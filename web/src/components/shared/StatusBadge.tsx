import type { ReactNode } from "react";

interface StatusBadgeProps {
  status: string | undefined | null;
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  healthy: { label: "Healthy", className: "autodoc-badge--success" },
  completed: { label: "Completed", className: "autodoc-badge--success" },
  running: { label: "Running", className: "autodoc-badge--warning" },
  failed: { label: "Failed", className: "autodoc-badge--error" },
  pending: { label: "Pending", className: "autodoc-badge--info" },
  cancelled: { label: "Cancelled", className: "autodoc-badge--neutral" },
  ready: { label: "Ready", className: "autodoc-badge--success" },
  stopped: { label: "Stopped", className: "autodoc-badge--neutral" },
};

export function StatusBadge({ status }: StatusBadgeProps): ReactNode {
  const normalized = (status ?? "").toLowerCase();
  const config = STATUS_CONFIG[normalized];

  if (!config) {
    return (
      <span className="autodoc-badge autodoc-badge--neutral">
        {status ?? "Unknown"}
      </span>
    );
  }

  return (
    <span className={`autodoc-badge ${config.className}`}>
      {config.label}
    </span>
  );
}
