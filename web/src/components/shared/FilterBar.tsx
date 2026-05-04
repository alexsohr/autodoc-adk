import type { ReactNode } from "react";

interface FilterOption {
  label: string;
  value: string;
  count?: number;
}

interface FilterBarProps {
  options: FilterOption[];
  value: string;
  onChange: (value: string) => void;
}

export function FilterBar({ options, value, onChange }: FilterBarProps): ReactNode {
  return (
    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
      {options.map((option) => {
        const isActive = option.value === value;
        return (
          <button
            key={option.value}
            data-testid={`filter-tab-${option.value}`}
            onClick={() => onChange(option.value)}
            style={{
              padding: "0.375rem 0.875rem",
              borderRadius: "9999px",
              border: "none",
              fontSize: "0.8125rem",
              fontWeight: 500,
              cursor: "pointer",
              transition: "background-color 200ms ease-out, color 200ms ease-out",
              background: isActive
                ? "var(--autodoc-primary)"
                : "var(--autodoc-surface-container)",
              color: isActive
                ? "var(--autodoc-on-primary)"
                : "var(--autodoc-on-surface)",
            }}
          >
            {option.label}
            {option.count != null && (
              <span
                style={{
                  marginLeft: "0.375rem",
                  opacity: 0.7,
                }}
              >
                ({option.count})
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
