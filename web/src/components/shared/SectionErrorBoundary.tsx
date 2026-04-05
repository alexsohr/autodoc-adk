import type { ReactNode } from "react";
import { Button } from "@salt-ds/core";
import { EmptyState } from "./EmptyState";

interface SectionErrorBoundaryProps {
  isLoading: boolean;
  isError: boolean;
  error?: Error | null;
  data?: unknown;
  onRetry?: () => void;
  emptyMessage?: string;
  emptyIcon?: ReactNode;
  emptyAction?: { label: string; onClick: () => void };
  children: ReactNode;
}

function isEmptyData(data: unknown): boolean {
  if (data == null) return true;
  if (Array.isArray(data) && data.length === 0) return true;
  return false;
}

function SkeletonBlock(): ReactNode {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", padding: "1rem 0" }}>
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          style={{
            height: "1rem",
            borderRadius: "6px",
            background: "var(--autodoc-surface-container-high)",
            width: `${80 - i * 15}%`,
            animation: "autodoc-skeleton-shimmer 1.5s ease-in-out infinite",
          }}
        />
      ))}
      <style>{`
        @keyframes autodoc-skeleton-shimmer {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function ErrorPanel({ error, onRetry }: { error?: Error | null; onRetry?: () => void }): ReactNode {
  return (
    <div
      style={{
        padding: "1.5rem",
        borderRadius: "12px",
        background: "var(--autodoc-error-container)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "0.75rem",
        textAlign: "center",
      }}
    >
      <p
        style={{
          color: "var(--autodoc-on-error-container)",
          fontSize: "0.875rem",
          margin: 0,
        }}
      >
        {error?.message ?? "Something went wrong"}
      </p>
      {onRetry && (
        <Button appearance="bordered" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function SectionErrorBoundary({
  isLoading,
  isError,
  error,
  data,
  onRetry,
  emptyMessage = "Nothing to show",
  emptyIcon,
  emptyAction,
  children,
}: SectionErrorBoundaryProps): ReactNode {
  if (isLoading) {
    return <SkeletonBlock />;
  }

  if (isError) {
    return <ErrorPanel error={error} onRetry={onRetry} />;
  }

  if (isEmptyData(data)) {
    return <EmptyState icon={emptyIcon} message={emptyMessage} action={emptyAction} />;
  }

  return <>{children}</>;
}
