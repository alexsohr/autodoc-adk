import type { ReactNode } from "react";
import { Button } from "@salt-ds/core";

interface EmptyStateProps {
  icon?: ReactNode;
  message: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ icon, message, action }: EmptyStateProps): ReactNode {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "3rem 1.5rem",
        gap: "1rem",
        textAlign: "center",
      }}
    >
      {icon && (
        <div
          style={{
            fontSize: "2.5rem",
            color: "var(--autodoc-on-surface-variant)",
            lineHeight: 1,
          }}
        >
          {icon}
        </div>
      )}

      <p
        style={{
          color: "var(--autodoc-on-surface-variant)",
          fontSize: "0.875rem",
          lineHeight: 1.6,
          margin: 0,
          maxWidth: "320px",
        }}
      >
        {message}
      </p>

      {action && (
        <Button appearance="bordered" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
