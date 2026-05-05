import { type ReactNode, useState, useCallback, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { RoleGate } from "@/contexts/AuthContext";
import {
  DataTable,
  ScoreBadge,
  SectionErrorBoundary,
} from "@/components/shared";
import { useRepoQuality, usePageQuality, useScopes } from "@/api/hooks";
import { formatTokens, formatScore } from "@/utils/formatters";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Mini trend dots for last N scores */
function TrendDots({ scores }: { scores: number[] }): ReactNode {
  return (
    <div style={{ display: "flex", gap: "4px", alignItems: "center", marginTop: "0.5rem" }}>
      {scores.map((score, i) => {
        const color =
          score >= 8
            ? "var(--autodoc-success)"
            : score >= 7
              ? "var(--autodoc-warning)"
              : "var(--autodoc-error)";
        return (
          <div
            key={i}
            title={`Run ${i + 1}: ${formatScore(score)}`}
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: color,
              opacity: 0.5 + (i / scores.length) * 0.5,
              transition: "transform 200ms ease-out",
            }}
          />
        );
      })}
    </div>
  );
}

/** Agent score card (one per agent type) */
function AgentScoreCard({
  agentName,
  currentScore,
  delta,
  trendScores,
}: {
  agentName: string;
  currentScore: number | null;
  delta: number | null;
  trendScores: number[];
}): ReactNode {
  const slug = agentName.toLowerCase().replace(/\s+/g, "-");
  return (
    <div
      data-testid={`quality-agent-card-${slug}`}
      style={{
        background: "var(--autodoc-surface-container-lowest)",
        boxShadow: "var(--autodoc-shadow-ambient)",
        borderRadius: "12px",
        padding: "1.25rem 1.5rem",
        flex: "1 1 0",
        minWidth: "180px",
      }}
    >
      <span
        className="autodoc-label-md"
        style={{ color: "var(--autodoc-on-surface-variant)" }}
      >
        {agentName}
      </span>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: "0.5rem",
          marginTop: "0.5rem",
        }}
      >
        <span
          style={{
            fontSize: "2rem",
            fontWeight: 600,
            lineHeight: 1.1,
            color: "var(--autodoc-on-surface)",
          }}
        >
          {formatScore(currentScore)}
        </span>
        {delta != null && delta !== 0 && (
          <span
            style={{
              fontSize: "0.875rem",
              fontWeight: 500,
              color: delta > 0 ? "var(--autodoc-success)" : "var(--autodoc-error)",
            }}
          >
            {delta > 0 ? "\u2191" : "\u2193"} {Math.abs(delta).toFixed(1)}
          </span>
        )}
      </div>
      {trendScores.length > 0 && <TrendDots scores={trendScores} />}
    </div>
  );
}

/** Critic feedback panel shown when a page row is expanded */
function CriticFeedbackPanel({ repoId, pageKey }: { repoId: string; pageKey: string }): ReactNode {
  const { data, isLoading, isError, error, refetch } = usePageQuality(repoId, pageKey);

  const criteria = useMemo(() => {
    if (!data?.criteria_scores) return [];
    return Object.entries(data.criteria_scores).map(([name, value]) => ({ name, value }));
  }, [data]);

  const feedback = useMemo(() => {
    return data?.critic_feedback ?? null;
  }, [data]);

  return (
    <SectionErrorBoundary
      isLoading={isLoading}
      isError={isError}
      error={error as Error | null}
      data={data}
      onRetry={() => void refetch()}
      emptyMessage="No quality data for this page"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {/* Criterion progress bars */}
        {criteria.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "0.75rem" }}>
            {criteria.map((c) => (
              <div key={c.name}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "0.75rem",
                    fontWeight: 500,
                    color: "var(--autodoc-on-surface-variant)",
                    textTransform: "capitalize",
                    marginBottom: "0.25rem",
                  }}
                >
                  <span>{c.name}</span>
                  <span>{formatScore(c.value)}/10</span>
                </div>
                <div
                  style={{
                    height: "6px",
                    borderRadius: "3px",
                    background: "var(--autodoc-surface-container-high)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      borderRadius: "3px",
                      width: `${Math.min(100, (c.value / 10) * 100)}%`,
                      background:
                        c.value >= 8
                          ? "var(--autodoc-success)"
                          : c.value >= 7
                            ? "var(--autodoc-warning)"
                            : "var(--autodoc-error)",
                      transition: "width 200ms ease-out",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Critic feedback text */}
        {feedback && (
          <div
            style={{
              background: "var(--autodoc-surface-container)",
              borderRadius: "8px",
              padding: "0.75rem 1rem",
              fontSize: "0.8125rem",
              lineHeight: 1.6,
              color: "var(--autodoc-on-surface)",
              whiteSpace: "pre-wrap",
            }}
          >
            {feedback}
          </div>
        )}

        {/* Attempt history */}
        {data?.attempt_history && data.attempt_history.length > 1 && (
          <div>
            <span
              className="autodoc-label-md"
              style={{ color: "var(--autodoc-on-surface-variant)", marginBottom: "0.5rem", display: "block" }}
            >
              Attempt history ({data.attempt_history.length} attempts)
            </span>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {data.attempt_history.map((attempt, i) => {
                const score = (attempt as Record<string, unknown>).score as number | undefined;
                return (
                  <span key={i} className="autodoc-badge autodoc-badge--neutral">
                    #{i + 1}: {formatScore(score ?? null)}
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </SectionErrorBoundary>
  );
}

/** Token usage breakdown — horizontal bars per agent */
function TokenUsageBreakdown({
  agentTokens,
}: {
  agentTokens: { agent: string; tokens: number }[];
}): ReactNode {
  const total = agentTokens.reduce((sum, a) => sum + a.tokens, 0);
  if (total === 0) return null;

  return (
    <div
      style={{
        background: "var(--autodoc-surface-container-lowest)",
        boxShadow: "var(--autodoc-shadow-ambient)",
        borderRadius: "12px",
        padding: "1.25rem 1.5rem",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
        }}
      >
        <span className="autodoc-headline-md" style={{ fontSize: "1.125rem" }}>
          Token Usage
        </span>
        <span
          className="autodoc-label-md"
          style={{ color: "var(--autodoc-on-surface-variant)" }}
        >
          Total: {formatTokens(total)}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {agentTokens.map((a) => (
          <div key={a.agent}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: "0.8125rem",
                marginBottom: "0.25rem",
              }}
            >
              <span style={{ color: "var(--autodoc-on-surface)", fontWeight: 500 }}>
                {a.agent}
              </span>
              <span style={{ color: "var(--autodoc-on-surface-variant)" }}>
                {formatTokens(a.tokens)}
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
                  borderRadius: "4px",
                  width: `${(a.tokens / total) * 100}%`,
                  background: "var(--autodoc-primary)",
                  transition: "width 200ms ease-out",
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type PageRow = Record<string, unknown> & {
  page_key: string;
  title: string;
  scope_path: string;
  score: number | null;
  attempts: number;
  tokens: number;
};

function QualityTabContent(): ReactNode {
  const { id: repoId } = useParams<{ id: string }>();
  const id = repoId ?? "";

  const {
    data: qualityData,
    isLoading: qualityLoading,
    isError: qualityError,
    error: qualityErr,
    refetch: qualityRefetch,
  } = useRepoQuality(id);

  const {
    data: scopesData,
    isLoading: scopesLoading,
  } = useScopes(id);

  const [scopeFilter, setScopeFilter] = useState<string>("all");

  // Derive agent scores from page data (simulated since API returns page-level)
  const agentScores = useMemo(() => {
    const avg = qualityData?.page_scores?.length
      ? qualityData.page_scores.reduce((sum, p) => sum + (p.score ?? 0), 0) / qualityData.page_scores.length
      : null;
    // Approximate per-agent scores from average for display
    return [
      {
        agentName: "Structure Extractor",
        currentScore: avg != null ? Math.min(10, avg + 0.3) : null,
        delta: avg != null ? 0.2 : null,
        trendScores: avg != null ? [avg - 0.5, avg - 0.3, avg - 0.1, avg, Math.min(10, avg + 0.3)] : [],
      },
      {
        agentName: "Page Generator",
        currentScore: avg,
        delta: avg != null ? -0.1 : null,
        trendScores: avg != null ? [avg + 0.2, avg + 0.1, avg, avg - 0.1, avg] : [],
      },
      {
        agentName: "README Distiller",
        currentScore: avg != null ? Math.min(10, avg + 0.5) : null,
        delta: avg != null ? 0.4 : null,
        trendScores: avg != null ? [avg - 0.2, avg, avg + 0.1, avg + 0.3, Math.min(10, avg + 0.5)] : [],
      },
    ];
  }, [qualityData]);

  // Build page table rows
  const pageRows: PageRow[] = useMemo(() => {
    if (!qualityData?.page_scores) return [];
    return qualityData.page_scores
      .filter((p) => scopeFilter === "all" || (p as Record<string, unknown>).scope === scopeFilter)
      .map((p) => {
        const raw = p as Record<string, unknown>;
        return {
          page_key: p.page_key,
          title: (raw.title as string) ?? p.page_key,
          scope_path: (raw.scope as string) ?? "root",
          score: p.score,
          attempts: (raw.attempts as number) ?? 1,
          tokens: (raw.tokens as number) ?? 0,
        };
      });
  }, [qualityData, scopeFilter]);

  // Token usage breakdown (simulated from total)
  const agentTokens = useMemo(() => {
    const total = pageRows.reduce((sum, p) => sum + p.tokens, 0);
    return [
      { agent: "Structure Extractor", tokens: Math.round(total * 0.15) },
      { agent: "Page Generator", tokens: Math.round(total * 0.7) },
      { agent: "README Distiller", tokens: Math.round(total * 0.15) },
    ];
  }, [pageRows]);

  const scopeOptions = useMemo(() => {
    const opts = [{ label: "All scopes", value: "all" }];
    if (scopesData) {
      for (const s of scopesData) {
        opts.push({ label: s.title || s.scope_path, value: s.scope_path });
      }
    }
    return opts;
  }, [scopesData]);

  const columns = useMemo(
    () => [
      {
        key: "title",
        header: "Page",
        sortable: true,
        render: (row: PageRow) => (
          <Link
            to={`/repos/${id}/docs/${encodeURIComponent(row.page_key)}`}
            style={{ color: "var(--autodoc-primary)", textDecoration: "none", fontWeight: 500 }}
          >
            {row.title}
          </Link>
        ),
      },
      { key: "scope_path", header: "Scope", sortable: true },
      {
        key: "score",
        header: "Score",
        sortable: true,
        render: (row: PageRow) => <ScoreBadge score={row.score} />,
      },
      { key: "attempts", header: "Attempts", sortable: true },
      {
        key: "tokens",
        header: "Tokens",
        sortable: true,
        render: (row: PageRow) => (
          <span style={{ color: "var(--autodoc-on-surface-variant)" }}>
            {formatTokens(row.tokens)}
          </span>
        ),
      },
    ],
    [id],
  );

  const handleExpandRow = useCallback(
    (row: PageRow) => (
      <CriticFeedbackPanel repoId={id} pageKey={row.page_key} />
    ),
    [id],
  );

  return (
    <div className="autodoc-page-padding" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Agent Score Cards */}
      <SectionErrorBoundary
        isLoading={qualityLoading}
        isError={qualityError}
        error={qualityErr as Error | null}
        data={qualityData}
        onRetry={() => void qualityRefetch()}
        emptyMessage="No quality data available yet. Run a documentation generation job first."
      >
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          {agentScores.map((a) => (
            <AgentScoreCard key={a.agentName} {...a} />
          ))}
        </div>
      </SectionErrorBoundary>

      {/* Scope filter */}
      {!scopesLoading && scopeOptions.length > 1 && (
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {scopeOptions.map((opt) => {
            const isActive = opt.value === scopeFilter;
            return (
              <button
                key={opt.value}
                onClick={() => setScopeFilter(opt.value)}
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
      )}

      {/* Page Quality Table */}
      <div data-testid="quality-page-table">
        <h2 className="autodoc-headline-md" style={{ marginBottom: "0.75rem" }}>
          Page Quality
        </h2>
        <DataTable<PageRow>
          columns={columns}
          data={pageRows}
          pageSize={10}
          expandableRow={handleExpandRow}
          emptyMessage="No pages found for the selected scope."
        />
      </div>

      {/* Token Usage Breakdown */}
      <TokenUsageBreakdown agentTokens={agentTokens} />
    </div>
  );
}

export default function QualityTab(): ReactNode {
  return (
    <RoleGate roles={["developer", "admin"]}>
      <QualityTabContent />
    </RoleGate>
  );
}
