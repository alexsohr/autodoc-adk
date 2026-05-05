import { type ReactNode, useState, useMemo } from "react";
import {
  MetricCard,
  SectionErrorBoundary,
} from "@/components/shared";
import { useAdminUsage } from "@/api/hooks";
import { formatTokens } from "@/utils/formatters";

// ---------------------------------------------------------------------------
// Time range options
// ---------------------------------------------------------------------------

const TIME_RANGES = [
  { label: "7 days", value: "7d" },
  { label: "30 days", value: "30d" },
  { label: "90 days", value: "90d" },
  { label: "All time", value: "all" },
] as const;

// ---------------------------------------------------------------------------
// Horizontal bar component
// ---------------------------------------------------------------------------

function HorizontalBar({
  label,
  value,
  maxValue,
  formattedValue,
  color,
}: {
  label: string;
  value: number;
  maxValue: number;
  formattedValue: string;
  color?: string;
}): ReactNode {
  const pct = maxValue > 0 ? (value / maxValue) * 100 : 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.8125rem",
        }}
      >
        <span style={{ fontWeight: 500, color: "var(--autodoc-on-surface)" }}>
          {label}
        </span>
        <span style={{ color: "var(--autodoc-on-surface-variant)" }}>
          {formattedValue}
        </span>
      </div>
      <div
        style={{
          height: "10px",
          borderRadius: "5px",
          background: "var(--autodoc-surface-container-high)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            borderRadius: "5px",
            width: `${Math.max(2, pct)}%`,
            background: color ?? "var(--autodoc-primary)",
            transition: "width 200ms ease-out",
          }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function UsageCostsPage(): ReactNode {
  const [range, setRange] = useState("30d");
  const { data, isLoading, isError, error, refetch } = useAdminUsage({ range });

  const maxRepoTokens = useMemo(
    () => Math.max(1, ...(data?.top_repos_by_tokens ?? []).map((r) => r.total_tokens)),
    [data],
  );

  const maxModelTokens = useMemo(
    () => Math.max(1, ...(data?.usage_by_model ?? []).map((m) => m.total_tokens)),
    [data],
  );

  const barColors = [
    "var(--autodoc-primary)",
    "var(--autodoc-primary-container)",
    "var(--autodoc-secondary)",
    "var(--autodoc-tertiary)",
    "var(--autodoc-primary-fixed-dim)",
  ];

  return (
    <div className="autodoc-page-padding" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header + time selector */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h1 className="autodoc-headline-lg" style={{ marginBottom: "0.25rem" }}>
            Usage & Costs
          </h1>
          <p
            data-testid="usage-subtitle"
            style={{ color: "var(--autodoc-on-surface-variant)", fontSize: "0.9375rem" }}
          >
            Token consumption, cost estimates, and efficiency metrics
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.25rem" }}>
          {TIME_RANGES.map((opt) => {
            const isActive = opt.value === range;
            return (
              <button
                key={opt.value}
                data-testid={`usage-range-${opt.label.toLowerCase().replace(/\s+/g, "-")}`}
                data-active={isActive ? "true" : undefined}
                aria-pressed={isActive}
                onClick={() => setRange(opt.value)}
                style={{
                  padding: "0.375rem 0.875rem",
                  borderRadius: "9999px",
                  border: "none",
                  fontSize: "0.8125rem",
                  fontWeight: 500,
                  cursor: "pointer",
                  transition: "background-color 200ms ease-out, color 200ms ease-out",
                  background: isActive ? "var(--autodoc-primary)" : "var(--autodoc-surface-container)",
                  color: isActive ? "var(--autodoc-on-primary)" : "var(--autodoc-on-surface)",
                }}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Metric cards */}
      <SectionErrorBoundary
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
        data={data}
        onRetry={() => void refetch()}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: "1rem",
          }}
        >
          <MetricCard
            testid="usage-metric-card-total-tokens"
            label="Total Tokens"
            value={formatTokens(data?.total_tokens ?? null)}
            subtitle={`Input: ${formatTokens(data?.total_input_tokens ?? null)} · Output: ${formatTokens(data?.total_output_tokens ?? null)}`}
          />
          <MetricCard
            testid="usage-metric-card-estimated-cost"
            label="Estimated Cost"
            value={`$${(data?.estimated_cost_usd ?? 0).toFixed(2)}`}
            subtitle="Based on input/output token rates"
          />
          <MetricCard
            testid="usage-metric-card-total-jobs"
            label="Total Jobs"
            value={String(data?.job_count ?? 0)}
            subtitle="Completed jobs in range"
          />
        </div>
      </SectionErrorBoundary>

      {/* Charts grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        {/* Top repos */}
        <SectionErrorBoundary
          isLoading={isLoading}
          isError={isError}
          error={error as Error | null}
          data={data?.top_repos_by_tokens}
          onRetry={() => void refetch()}
          emptyMessage="No repository usage data"
        >
          <div
            style={{
              background: "var(--autodoc-surface-container-lowest)",
              boxShadow: "var(--autodoc-shadow-ambient)",
              borderRadius: "12px",
              padding: "1.5rem",
            }}
          >
            <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: "1rem" }}>
              Top Repositories
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {(data?.top_repos_by_tokens ?? []).map((repo, i) => (
                <HorizontalBar
                  key={repo.repository_id}
                  label={repo.name}
                  value={repo.total_tokens}
                  maxValue={maxRepoTokens}
                  formattedValue={formatTokens(repo.total_tokens)}
                  color={barColors[i % barColors.length]}
                />
              ))}
            </div>
          </div>
        </SectionErrorBoundary>

        {/* Usage by model */}
        <SectionErrorBoundary
          isLoading={isLoading}
          isError={isError}
          error={error as Error | null}
          data={data?.usage_by_model}
          onRetry={() => void refetch()}
          emptyMessage="No model usage data"
        >
          <div
            style={{
              background: "var(--autodoc-surface-container-lowest)",
              boxShadow: "var(--autodoc-shadow-ambient)",
              borderRadius: "12px",
              padding: "1.5rem",
            }}
          >
            <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: "1rem" }}>
              Usage by Model
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {(data?.usage_by_model ?? []).map((model, i) => (
                <HorizontalBar
                  key={model.model}
                  label={model.model}
                  value={model.total_tokens}
                  maxValue={maxModelTokens}
                  formattedValue={`${formatTokens(model.total_tokens)} (${model.calls} calls)`}
                  color={barColors[i % barColors.length]}
                />
              ))}
            </div>
          </div>
        </SectionErrorBoundary>
      </div>

      {/* Cost efficiency tip */}
      <div
        data-testid="usage-cost-efficiency-tip"
        style={{
          background: "var(--autodoc-info-bg)",
          borderRadius: "12px",
          padding: "1.25rem 1.5rem",
          display: "flex",
          gap: "1rem",
          alignItems: "flex-start",
        }}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="var(--autodoc-info)"
          style={{ flexShrink: 0, marginTop: "2px" }}
        >
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
        </svg>
        <div>
          <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--autodoc-info)", marginBottom: "0.25rem" }}>
            Cost Efficiency Tip
          </h3>
          <p
            style={{
              fontSize: "0.8125rem",
              lineHeight: 1.6,
              color: "var(--autodoc-on-surface)",
              margin: 0,
            }}
          >
            Switch to incremental generation mode for repositories with stable architectures.
            Incremental updates typically use 60-80% fewer tokens compared to full regeneration,
            while maintaining the same quality scores. Configure per-repo schedules in Settings.
          </p>
        </div>
      </div>
    </div>
  );
}
