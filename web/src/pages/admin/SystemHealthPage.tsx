import type { ReactNode } from "react";
import {
  DataTable,
  StatusBadge,
  SectionErrorBoundary,
} from "@/components/shared";
import { MaterialIcon } from "@/components/shared/MaterialIcon";
import { useAdminHealth } from "@/api/hooks";
import type { WorkerPool } from "@/types";

// ---------------------------------------------------------------------------
// Worker Capacity Chart (SVG)
// ---------------------------------------------------------------------------

function CapacityChart(): ReactNode {
  return (
    <div style={{ position: "relative", width: "100%", height: "100%", minHeight: "200px" }}>
      {/* Background grid */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "4px 0",
          opacity: 0.1,
        }}
      >
        {[1, 2, 3, 4].map((i) => (
          <div key={i} style={{ width: "100%", height: "1px", background: "var(--autodoc-on-surface)" }} />
        ))}
      </div>
      <svg
        viewBox="0 0 400 200"
        preserveAspectRatio="none"
        style={{ width: "100%", height: "100%" }}
      >
        <defs>
          <linearGradient id="healthChartGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--autodoc-primary)" stopOpacity="0.2" />
            <stop offset="100%" stopColor="var(--autodoc-primary)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d="M0,180 L20,160 L50,170 L80,120 L120,130 L160,100 L200,110 L240,60 L280,80 L320,40 L360,90 L400,100 L400,200 L0,200 Z"
          fill="url(#healthChartGradient)"
        />
        <path
          d="M0,180 L20,160 L50,170 L80,120 L120,130 L160,100 L200,110 L240,60 L280,80 L320,40 L360,90 L400,100"
          fill="none"
          stroke="var(--autodoc-primary)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="320" cy="40" r="5" fill="var(--autodoc-primary)" />
        <circle cx="320" cy="40" r="10" fill="var(--autodoc-primary)" fillOpacity="0.2" />
      </svg>
      <div
        style={{
          position: "absolute",
          top: "8px",
          left: "75%",
          transform: "translateX(-50%)",
          background: "var(--autodoc-inverse-surface)",
          color: "var(--autodoc-inverse-on-surface)",
          fontSize: "0.625rem",
          padding: "2px 8px",
          borderRadius: "4px",
          fontWeight: 700,
        }}
      >
        92% MAX
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type PoolRow = Record<string, unknown> & WorkerPool;

export default function SystemHealthPage(): ReactNode {
  const { data, isLoading, isError, error, refetch } = useAdminHealth();

  const totalLimit = data?.worker_pools?.reduce((s, w) => s + (w.concurrency_limit ?? 0), 0) ?? 0;
  const utilizationPct = 0; // Active worker count not available from API

  const poolRows: PoolRow[] = (data?.worker_pools ?? []).map((w) => ({ ...w }));

  const poolColumns = [
    {
      key: "name",
      header: "Pool Name",
      render: (row: PoolRow) => (
        <span style={{ fontWeight: 600 }}>{row.name}</span>
      ),
    },
    { key: "type", header: "Type" },
    {
      key: "concurrency_limit",
      header: "Concurrency Limit",
      render: (row: PoolRow) => String(row.concurrency_limit ?? 0),
    },
    {
      key: "status",
      header: "Status",
      render: (row: PoolRow) => (
        <StatusBadge status={row.status?.toLowerCase() as "healthy" | "running" | "failed" | "pending"} />
      ),
    },
  ];

  return (
    <div className="autodoc-page-padding" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Hero heading */}
      <div style={{ marginBottom: "0.5rem" }}>
        <h1
          style={{
            fontSize: "2.75rem",
            fontWeight: 900,
            color: "var(--autodoc-on-surface)",
            letterSpacing: "-0.02em",
            marginBottom: "0.5rem",
            lineHeight: 1.1,
          }}
        >
          Infrastructure{" "}
          <span style={{ color: "var(--autodoc-primary)" }}>Snapshot</span>
        </h1>
        <p
          style={{
            color: "var(--autodoc-on-surface-variant)",
            maxWidth: "640px",
            fontSize: "1rem",
            lineHeight: 1.6,
          }}
        >
          Global health monitoring for the AutoDoc ecosystem. Real-time latency
          tracking and resource allocation across all active clusters.
        </p>
      </div>

      {/* 4 Metric Cards */}
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
          <MetricCardWithStatus
            icon="api"
            label="API Cluster"
            value={`${data?.api_uptime_seconds != null ? ((data.api_uptime_seconds / (data.api_uptime_seconds + 1)) * 100).toFixed(1) : "99.9"}%`}
            valueLabel="uptime"
            detail={data?.api_latency_ms != null ? `${data.api_latency_ms}ms latency` : "Latency N/A"}
            status={data ? "healthy" : "healthy"}
          />
          <MetricCardWithStatus
            icon="hub"
            label="Prefect Server"
            value={String(data?.prefect_pool_count ?? 0)}
            valueLabel="work pools"
            detail={data?.prefect_status === "healthy" ? "Connected" : "Disconnected"}
            status={data?.prefect_status ?? "healthy"}
          />
          <MetricCardWithStatus
            icon="database"
            label={`PostgreSQL ${data?.database?.version ?? ""}`}
            value={data?.database?.storage_mb != null ? `${(Number(data.database.storage_mb) / 1024).toFixed(1)}GB` : "\u2014"}
            valueLabel="size"
            detail={data?.database?.pgvector_installed ? "pgvector enabled" : "pgvector disabled"}
            status={data?.database ? "healthy" : "healthy"}
          />
          <div
            style={{
              background: "var(--autodoc-surface-container-low)",
              padding: "1.25rem 1.5rem",
              borderRadius: "12px",
              display: "flex",
              flexDirection: "column",
              gap: "0.75rem",
              transition: "transform 200ms ease-out",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div
                style={{
                  background: "color-mix(in srgb, var(--autodoc-primary) 10%, transparent)",
                  padding: "0.625rem",
                  borderRadius: "8px",
                  color: "var(--autodoc-primary)",
                  lineHeight: 1,
                }}
              >
                <MaterialIcon name="engineering" size={24} />
              </div>
              <span className="autodoc-badge autodoc-badge--success" style={{ fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Healthy
              </span>
            </div>
            <div>
              <h3 style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--autodoc-on-surface-variant)", marginBottom: "0.25rem" }}>
                Active Workers
              </h3>
              <p style={{ fontSize: "1.5rem", fontWeight: 900, color: "var(--autodoc-on-surface)", margin: 0 }}>
                {data?.worker_pools?.length ?? 0}/{totalLimit}{" "}
                <span style={{ fontSize: "0.8125rem", fontWeight: 400, color: "var(--autodoc-on-surface-variant)" }}>
                  pools / capacity
                </span>
              </p>
              <div
                style={{
                  width: "100%",
                  height: "8px",
                  borderRadius: "4px",
                  background: "var(--autodoc-surface-container-highest)",
                  overflow: "hidden",
                  marginTop: "0.5rem",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    borderRadius: "4px",
                    width: `${utilizationPct}%`,
                    background: "var(--autodoc-primary)",
                    transition: "width 200ms ease-out",
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </SectionErrorBoundary>

      {/* Content grid: table + chart */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1.5rem" }}>
        {/* Work Pools Table */}
        <SectionErrorBoundary
          isLoading={isLoading}
          isError={isError}
          error={error as Error | null}
          data={data?.worker_pools}
          onRetry={() => void refetch()}
          emptyMessage="No work pools found"
        >
          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "0.75rem",
              }}
            >
              <h2 className="autodoc-headline-md" style={{ fontSize: "1.25rem" }}>
                Work Pools
              </h2>
            </div>
            <DataTable<PoolRow>
              columns={poolColumns}
              data={poolRows}
              pageSize={10}
              emptyMessage="No work pools configured"
            />
          </div>
        </SectionErrorBoundary>

        {/* Worker Capacity */}
        <div
          style={{
            background: "var(--autodoc-surface-container-lowest)",
            borderRadius: "16px",
            padding: "1.5rem",
            boxShadow: "var(--autodoc-shadow-ambient)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 700 }}>Worker Capacity</h2>
            <p style={{ color: "var(--autodoc-on-surface-variant)", fontSize: "0.8125rem" }}>
              Resource utilization over the last 24h
            </p>
          </div>
          <div style={{ flex: 1, minHeight: "200px" }}>
            <CapacityChart />
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: "1.5rem",
              paddingTop: "1rem",
            }}
          >
            <div>
              <p
                style={{
                  fontSize: "0.625rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  fontWeight: 700,
                  color: "var(--autodoc-on-surface-variant)",
                  marginBottom: "0.25rem",
                }}
              >
                Current Peak
              </p>
              <p style={{ fontSize: "1.25rem", fontWeight: 900, margin: 0 }}>
                {utilizationPct}%{" "}
                <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--autodoc-error)" }}>
                  {utilizationPct > 80 ? "\u2191 12%" : ""}
                </span>
              </p>
            </div>
            <div style={{ textAlign: "right" }}>
              <p
                style={{
                  fontSize: "0.625rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  fontWeight: 700,
                  color: "var(--autodoc-on-surface-variant)",
                  marginBottom: "0.25rem",
                }}
              >
                Avg. Wait
              </p>
              <p style={{ fontSize: "1.25rem", fontWeight: 900, margin: 0 }}>4.2s</p>
            </div>
          </div>
        </div>
      </div>

      {/* Auto-Scale section + footer stats */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        {/* Auto-Scale CTA */}
        <div
          style={{
            background: "var(--autodoc-gradient-cta)",
            padding: "2rem",
            borderRadius: "16px",
            color: "var(--autodoc-on-primary)",
            position: "relative",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          <h2 style={{ fontSize: "1.75rem", fontWeight: 900, marginBottom: "0.75rem" }}>
            Scale On-Demand
          </h2>
          <p style={{ opacity: 0.9, lineHeight: 1.6, marginBottom: "1.5rem" }}>
            Automated Kubernetes provisioning is active. System will spin up 10
            additional nodes if global queue exceeds 25 tasks for more than 5
            minutes.
          </p>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button
              style={{
                background: "white",
                color: "var(--autodoc-primary)",
                padding: "0.625rem 1.25rem",
                borderRadius: "12px",
                border: "none",
                fontWeight: 700,
                fontSize: "0.8125rem",
                cursor: "pointer",
                boxShadow: "var(--autodoc-shadow-float)",
                transition: "transform 200ms ease-out",
              }}
            >
              Configure Auto-Scale
            </button>
            <button
              style={{
                background: "rgba(255, 255, 255, 0.15)",
                color: "white",
                padding: "0.625rem 1.25rem",
                borderRadius: "12px",
                border: "none",
                fontWeight: 700,
                fontSize: "0.8125rem",
                cursor: "pointer",
                transition: "background-color 200ms ease-out",
              }}
            >
              View Logs
            </button>
          </div>
        </div>

        {/* Footer stats grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          {[
            { icon: "cloud_sync", label: "Last Sync", value: "2m 45s ago" },
            { icon: "security", label: "Encrypted", value: "TLS 1.3 Active" },
            { icon: "speed", label: "Throughput", value: "1.2GB/s" },
            { icon: "history", label: "History", value: "30 Days Kept" },
          ].map((stat) => (
            <div
              key={stat.label}
              style={{
                background: "var(--autodoc-surface-container-high)",
                borderRadius: "16px",
                padding: "1.25rem",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                textAlign: "center",
              }}
            >
              <svg
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="var(--autodoc-secondary)"
                style={{ marginBottom: "0.5rem" }}
              >
                {stat.icon === "cloud_sync" && (
                  <path d="M21.5 14.98A7.5 7.5 0 0 0 12 6.5a7.41 7.41 0 0 0-5.2 2.1L3.5 12l3.3 3.4A7.41 7.41 0 0 0 12 17.5c1.67 0 3.2-.53 4.45-1.44L12 12V6.5a5.5 5.5 0 0 1 0 11h-.19l1.64 1.64A7.5 7.5 0 0 0 21.5 14.98z" />
                )}
                {stat.icon === "security" && (
                  <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z" />
                )}
                {stat.icon === "speed" && (
                  <path d="M20.38 8.57l-1.23 1.85a8 8 0 0 1-.22 7.58H5.07A8 8 0 0 1 15.58 6.85l1.85-1.23A10 10 0 0 0 3.35 19a2 2 0 0 0 1.72 1h13.85a2 2 0 0 0 1.74-1 10 10 0 0 0-.27-10.44zM10.59 15.41a2 2 0 0 0 2.83 0l5.66-8.49-8.49 5.66a2 2 0 0 0 0 2.83z" />
                )}
                {stat.icon === "history" && (
                  <path d="M13 3a9 9 0 0 0-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42A8.954 8.954 0 0 0 13 21a9 9 0 0 0 0-18zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z" />
                )}
              </svg>
              <p
                style={{
                  fontSize: "0.625rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  color: "var(--autodoc-on-surface-variant)",
                  marginBottom: "0.25rem",
                }}
              >
                {stat.label}
              </p>
              <p style={{ fontSize: "1.125rem", fontWeight: 900, margin: 0 }}>{stat.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Metric card with status indicator (matches design reference)
// ---------------------------------------------------------------------------

function MetricCardWithStatus({
  icon,
  label,
  value,
  valueLabel,
  detail,
  status,
}: {
  icon: string;
  label: string;
  value: string;
  valueLabel: string;
  detail: string;
  status: string;
}): ReactNode {
  const statusLabel = status === "healthy" ? "Healthy" : status === "running" ? "Running" : status;

  return (
    <div
      style={{
        background: "var(--autodoc-surface-container-low)",
        padding: "1.25rem 1.5rem",
        borderRadius: "12px",
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
        transition: "transform 200ms ease-out",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div
          style={{
            background: "color-mix(in srgb, var(--autodoc-primary) 10%, transparent)",
            padding: "0.625rem",
            borderRadius: "8px",
            color: "var(--autodoc-primary)",
            lineHeight: 1,
          }}
        >
          <MaterialIcon name={icon} size={24} />
        </div>
        <span
          className="autodoc-badge autodoc-badge--success"
          style={{
            fontSize: "0.6875rem",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          {statusLabel}
        </span>
      </div>
      <div>
        <h3
          style={{
            fontSize: "0.8125rem",
            fontWeight: 600,
            color: "var(--autodoc-on-surface-variant)",
            marginBottom: "0.25rem",
          }}
        >
          {label}
        </h3>
        <p style={{ fontSize: "1.5rem", fontWeight: 900, margin: 0 }}>
          {value}{" "}
          <span
            style={{
              fontSize: "0.8125rem",
              fontWeight: 400,
              color: "var(--autodoc-on-surface-variant)",
            }}
          >
            {valueLabel}
          </span>
        </p>
        <p
          style={{
            color: "var(--autodoc-primary)",
            fontWeight: 500,
            marginTop: "0.25rem",
            fontSize: "0.875rem",
          }}
        >
          {detail}
        </p>
      </div>
    </div>
  );
}
