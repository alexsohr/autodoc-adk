import {
  type ReactNode,
  useState,
  useCallback,
  useEffect,
  useMemo,
} from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { useSearch, useScopes } from "@/api/hooks";
import {
  FilterBar,
  SectionErrorBoundary,
  EmptyState,
} from "@/components/shared";
import type { SearchResult } from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SEARCH_MODES = [
  { label: "Hybrid", value: "hybrid" },
  { label: "Semantic", value: "semantic" },
  { label: "Full Text", value: "fulltext" },
];

const PAGE_SIZE = 10;

// ---------------------------------------------------------------------------
// Relevance color helpers
// ---------------------------------------------------------------------------

function getRelevanceClass(score: number): string {
  if (score >= 0.8) return "autodoc-badge--success";
  if (score >= 0.6) return "autodoc-badge--warning";
  return "autodoc-badge--neutral";
}

function getCardOpacity(score: number): number {
  if (score >= 0.8) return 1;
  if (score >= 0.6) return 0.88;
  return 0.72;
}

// ---------------------------------------------------------------------------
// SearchResultCard
// ---------------------------------------------------------------------------

function SearchResultCard({
  result,
  repoId,
}: {
  result: SearchResult;
  repoId: string;
}): ReactNode {
  const breadcrumb = [result.scope_path, ...(result.best_chunk_heading_path ?? [])].join(" / ");

  return (
    <div
      style={{
        background: "var(--autodoc-surface-container-lowest)",
        borderRadius: "12px",
        padding: "1.25rem 1.5rem",
        boxShadow: "var(--autodoc-shadow-ambient)",
        opacity: getCardOpacity(result.score),
        transition: "opacity 200ms ease-out, box-shadow 200ms ease-out",
        display: "flex",
        flexDirection: "column",
        gap: "0.625rem",
      }}
    >
      {/* Title row */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "1rem",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <Link
            to={`/repos/${repoId}/docs/${encodeURIComponent(result.page_key)}`}
            style={{
              fontSize: "1rem",
              fontWeight: 700,
              color: "var(--autodoc-on-surface)",
              textDecoration: "none",
              transition: "color 200ms ease-out",
            }}
          >
            {result.title}
          </Link>
          <div
            style={{
              fontSize: "0.75rem",
              color: "var(--autodoc-outline)",
              marginTop: "0.25rem",
            }}
          >
            {breadcrumb}
          </div>
        </div>
        <span className={`autodoc-badge ${getRelevanceClass(result.score)}`}>
          {(result.score * 100).toFixed(0)}%
        </span>
      </div>

      {/* Snippet */}
      <p
        style={{
          fontSize: "0.875rem",
          lineHeight: 1.7,
          color: "var(--autodoc-on-surface-variant)",
          margin: 0,
        }}
        dangerouslySetInnerHTML={{ __html: result.snippet }}
      />

      {/* Footer meta */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
          fontSize: "0.75rem",
          color: "var(--autodoc-outline)",
        }}
      >
        <span>{result.best_chunk_content}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SearchTab (default export)
// ---------------------------------------------------------------------------

export default function SearchTab(): ReactNode {
  const { id: repoId = "" } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  // Read initial values from URL
  const initialQuery = searchParams.get("q") || "";
  const initialType = searchParams.get("type") || "hybrid";
  const initialScope = searchParams.get("scope") || "";

  const [inputValue, setInputValue] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery);
  const [searchType, setSearchType] = useState(initialType);
  const [scopeFilter, setScopeFilter] = useState(initialScope);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const { data: scopes } = useScopes(repoId);

  // Sync state to URL
  useEffect(() => {
    const params: Record<string, string> = {};
    if (query) params.q = query;
    if (searchType !== "hybrid") params.type = searchType;
    if (scopeFilter) params.scope = scopeFilter;
    setSearchParams(params, { replace: true });
  }, [query, searchType, scopeFilter, setSearchParams]);

  const searchParams2 = useMemo(
    () => ({
      query,
      type: searchType,
      scope: scopeFilter || undefined,
    }),
    [query, searchType, scopeFilter],
  );

  const {
    data: searchResponse,
    isLoading,
    isError,
    error,
  } = useSearch(repoId, searchParams2);

  const results = searchResponse?.results ?? [];
  const visibleResults = results.slice(0, visibleCount);
  const hasMore = visibleCount < results.length;

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setQuery(inputValue.trim());
      setVisibleCount(PAGE_SIZE);
    },
    [inputValue],
  );

  const handleTypeChange = useCallback(
    (value: string) => {
      setSearchType(value);
      setVisibleCount(PAGE_SIZE);
    },
    [],
  );

  const handleLoadMore = useCallback(() => {
    setVisibleCount((c) => c + PAGE_SIZE);
  }, []);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "1.5rem",
        maxWidth: "860px",
      }}
    >
      {/* Search form */}
      <form
        onSubmit={handleSubmit}
        style={{
          display: "flex",
          gap: "0.75rem",
        }}
      >
        <input
          type="text"
          data-testid="search-tab-input"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Search documentation..."
          style={{
            flex: 1,
            padding: "0.75rem 1rem",
            borderRadius: "12px",
            border: "none",
            background: "var(--autodoc-surface-container-high)",
            color: "var(--autodoc-on-surface)",
            fontSize: "0.9375rem",
            fontFamily: "inherit",
            outline: "none",
            transition: "box-shadow 200ms ease-out",
          }}
        />
        <button
          type="submit"
          data-testid="search-tab-submit"
          disabled={!inputValue.trim()}
          style={{
            padding: "0.75rem 1.5rem",
            borderRadius: "12px",
            border: "none",
            background: inputValue.trim()
              ? "var(--autodoc-gradient-cta)"
              : "var(--autodoc-surface-container)",
            color: inputValue.trim()
              ? "var(--autodoc-on-primary)"
              : "var(--autodoc-outline)",
            fontWeight: 600,
            fontSize: "0.875rem",
            cursor: inputValue.trim() ? "pointer" : "default",
            fontFamily: "inherit",
            transition: "opacity 200ms ease-out, transform 200ms ease-out",
          }}
        >
          Search
        </button>
      </form>

      {/* Filter bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "0.75rem",
        }}
      >
        <FilterBar
          options={SEARCH_MODES}
          value={searchType}
          onChange={handleTypeChange}
        />

        {/* Scope filter */}
        {scopes && scopes.length > 1 && (
          <select
            value={scopeFilter}
            onChange={(e) => {
              setScopeFilter(e.target.value);
              setVisibleCount(PAGE_SIZE);
            }}
            style={{
              padding: "0.375rem 0.75rem",
              borderRadius: "8px",
              border: "none",
              background: "var(--autodoc-surface-container)",
              color: "var(--autodoc-on-surface)",
              fontSize: "0.8125rem",
              fontFamily: "inherit",
              cursor: "pointer",
            }}
          >
            <option value="">All scopes</option>
            {scopes.map((s) => (
              <option key={s.scope_path} value={s.scope_path}>
                {s.title}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Results header */}
      {query && searchResponse && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "0.8125rem",
            color: "var(--autodoc-on-surface-variant)",
          }}
        >
          <span>
            <strong style={{ color: "var(--autodoc-on-surface)" }}>
              {searchResponse.total}
            </strong>{" "}
            result{searchResponse.total !== 1 ? "s" : ""} found
          </span>
          <span style={{ color: "var(--autodoc-outline)" }}>
            {searchResponse.search_type}
          </span>
        </div>
      )}

      {/* Results */}
      {!query && (
        <EmptyState message="Enter a search query to find documentation pages, code references, and more." />
      )}

      {query && (
        // Wrapper carries a testid only when the boundary is in its error
        // state so e2e specs can assert deterministically on the search-error
        // branch (see PTS-2.4 "results OR error/empty state" criterion).
        <div {...(isError ? { "data-testid": "search-error-state" } : {})}>
          <SectionErrorBoundary
            isLoading={isLoading}
            isError={isError}
            error={error instanceof Error ? error : null}
            data={results.length > 0 ? results : undefined}
            emptyMessage={`No results found for "${query}". Try a different search term or mode.`}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
              }}
            >
              {visibleResults.map((result) => (
                <SearchResultCard
                  key={result.page_key + (result.best_chunk_content ?? "")}
                  result={result}
                  repoId={repoId}
                />
              ))}

              {/* Load more */}
              {hasMore && (
                <button
                  onClick={handleLoadMore}
                  style={{
                    alignSelf: "center",
                    padding: "0.625rem 2rem",
                    borderRadius: "9999px",
                    border: "none",
                    background: "var(--autodoc-surface-container)",
                    color: "var(--autodoc-primary)",
                    fontWeight: 600,
                    fontSize: "0.875rem",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    transition:
                      "background-color 200ms ease-out, transform 200ms ease-out",
                  }}
                >
                  Load more ({results.length - visibleCount} remaining)
                </button>
              )}
            </div>
          </SectionErrorBoundary>
        </div>
      )}
    </div>
  );
}
