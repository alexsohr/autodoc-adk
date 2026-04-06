import { Card } from "@salt-ds/core";
import { MaterialIcon } from "./MaterialIcon";

interface MetricCardProps {
  label: string;
  value: string | number;
  delta?: string;
  subtitle?: string;
  icon?: string;
}

export function MetricCard({ label, value, delta, subtitle, icon }: MetricCardProps) {
  return (
    <Card
      style={{
        padding: "var(--autodoc-spacing-lg)",
        background: "var(--autodoc-surface-container-low)",
        boxShadow: "var(--autodoc-shadow-ambient)",
        borderRadius: "var(--autodoc-radius-xl)",
      }}
    >
      {icon && (
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: "var(--autodoc-radius-xl)",
            background: "var(--autodoc-primary-fixed)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: "var(--autodoc-spacing-sm)",
          }}
        >
          <MaterialIcon name={icon} size={20} />
        </div>
      )}
      <div className="autodoc-label-md" style={{ color: "var(--autodoc-on-surface-variant)" }}>
        {label}
      </div>
      <div style={{ fontSize: "1.5rem", fontWeight: 700, marginTop: "0.25rem" }}>
        {value}
      </div>
      {delta && (
        <div
          style={{
            fontSize: "0.75rem",
            color: delta.startsWith("+") || delta.startsWith("↑")
              ? "var(--autodoc-success)"
              : "var(--autodoc-error)",
            marginTop: "0.25rem",
          }}
        >
          {delta}
        </div>
      )}
      {subtitle && (
        <div style={{ fontSize: "0.75rem", color: "var(--autodoc-on-surface-variant)", marginTop: "0.25rem" }}>
          {subtitle}
        </div>
      )}
    </Card>
  );
}
