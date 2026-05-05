import { useRef, useEffect, useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { SearchIcon } from "@salt-ds/icons";

import { api } from "@/api/client";
import { useRepositories } from "@/api/hooks";
import type { SearchResult } from "@/types";

import "./ContextSearch.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GroupedResults {
  repoId: string;
  repoName: string;
  results: SearchResult[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ContextSearch() {
  const location = useLocation();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [isFocused, setIsFocused] = useState(false);
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [grouped, setGrouped] = useState<GroupedResults[]>([]);
  const [hasSearched, setHasSearched] = useState(false);

  const { data: repositories } = useRepositories();

  // Determine placeholder based on current route
  const placeholder = getPlaceholder(location.pathname);

  // Whether the dropdown should be visible
  const showDropdown = isFocused && query.trim().length > 0 && (isSearching || hasSearched);

  // ------ Debounced search ------
  const performSearch = useCallback(
    async (searchQuery: string) => {
      if (!searchQuery.trim() || !repositories || repositories.length === 0) {
        setGrouped([]);
        setHasSearched(false);
        setIsSearching(false);
        return;
      }

      setIsSearching(true);
      setHasSearched(false);

      // Cap at first 5 repos
      const repos = repositories.slice(0, 5);

      try {
        const promises = repos.map((repo) =>
          api
            .get<{ results: SearchResult[] }>(`/documents/${repo.id}/search`, {
              params: { q: searchQuery, limit: 5 },
            })
            .then((res) => ({
              repoId: repo.id,
              repoName: repo.name,
              results: res.results,
            }))
            .catch(() => ({
              repoId: repo.id,
              repoName: repo.name,
              results: [] as SearchResult[],
            })),
        );

        const results = await Promise.all(promises);
        setGrouped(results.filter((g) => g.results.length > 0));
      } catch {
        setGrouped([]);
      } finally {
        setIsSearching(false);
        setHasSearched(true);
      }
    },
    [repositories],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setQuery(value);

      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      if (!value.trim()) {
        setGrouped([]);
        setHasSearched(false);
        setIsSearching(false);
        return;
      }

      debounceRef.current = setTimeout(() => {
        void performSearch(value);
      }, 300);
    },
    [performSearch],
  );

  // ------ Result click handler ------
  const handleResultClick = useCallback(
    (repoId: string, pageKey: string) => {
      navigate(`/repos/${repoId}/docs/${encodeURIComponent(pageKey)}`);
      setQuery("");
      setGrouped([]);
      setHasSearched(false);
      inputRef.current?.blur();
    },
    [navigate],
  );

  // ------ Close on Escape ------
  const handleInputKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setQuery("");
      setGrouped([]);
      setHasSearched(false);
      inputRef.current?.blur();
    }
  }, []);

  // ------ Blur with delay (allow clicking results) ------
  const handleBlur = useCallback(() => {
    setTimeout(() => {
      setIsFocused(false);
    }, 200);
  }, []);

  // ------ Cmd+K / Ctrl+K to focus ------
  const handleGlobalKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      inputRef.current?.focus();
    }
  }, []);

  useEffect(() => {
    document.addEventListener("keydown", handleGlobalKeyDown);
    return () => document.removeEventListener("keydown", handleGlobalKeyDown);
  }, [handleGlobalKeyDown]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  return (
    <div
      className={`context-search ${isFocused ? "context-search--focused" : ""}`}
      style={{ position: "relative" }}
    >
      <SearchIcon size={1} className="context-search__icon" />
      <input
        ref={inputRef}
        type="text"
        data-testid="topbar-global-search"
        className="context-search__input"
        placeholder={placeholder}
        value={query}
        onChange={handleInputChange}
        onKeyDown={handleInputKeyDown}
        onFocus={() => setIsFocused(true)}
        onBlur={handleBlur}
      />
      <kbd className="context-search__shortcut">
        <span className="context-search__shortcut-key">&#8984;K</span>
      </kbd>

      {/* ----- Results dropdown ----- */}
      {showDropdown && (
        <div ref={dropdownRef} style={dropdownStyles}>
          {isSearching && (
            <div style={messageStyles}>
              <span style={spinnerStyles} />
              Searching...
            </div>
          )}

          {!isSearching && hasSearched && grouped.length === 0 && (
            <div style={messageStyles}>No results found</div>
          )}

          {!isSearching &&
            grouped.map((group) => (
              <div key={group.repoId} style={groupStyles}>
                <div style={groupHeaderStyles}>{group.repoName}</div>
                {group.results.map((result) => (
                  <button
                    key={`${group.repoId}-${result.page_key}`}
                    type="button"
                    style={resultItemStyles}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleResultClick(group.repoId, result.page_key);
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.backgroundColor =
                        "var(--autodoc-surface-container-high)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.backgroundColor =
                        "transparent";
                    }}
                  >
                    <div style={resultTitleStyles}>{result.title}</div>
                    <div style={resultSnippetStyles}>{result.snippet}</div>
                  </button>
                ))}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline styles — uses var(--autodoc-*) tokens for TopBar/AppLayout consistency
// ---------------------------------------------------------------------------

const dropdownStyles: React.CSSProperties = {
  position: "absolute",
  top: "calc(100% + 0.5rem)",
  left: 0,
  right: 0,
  zIndex: 1000,
  maxHeight: "24rem",
  overflowY: "auto",
  backgroundColor: "var(--autodoc-surface-container)",
  borderRadius: "0.75rem",
  boxShadow: "0 8px 32px rgba(0, 0, 0, 0.24)",
  backdropFilter: "blur(var(--autodoc-glass-blur))",
  WebkitBackdropFilter: "blur(var(--autodoc-glass-blur))",
  padding: "0.5rem 0",
};

const messageStyles: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
  padding: "0.75rem 1rem",
  fontSize: "0.8125rem",
  color: "var(--autodoc-on-surface-variant)",
};

const spinnerStyles: React.CSSProperties = {
  display: "inline-block",
  width: "0.875rem",
  height: "0.875rem",
  border: "2px solid var(--autodoc-on-surface-variant)",
  borderTopColor: "transparent",
  borderRadius: "50%",
  animation: "spin 0.6s linear infinite",
};

const groupStyles: React.CSSProperties = {
  padding: "0.25rem 0",
};

const groupHeaderStyles: React.CSSProperties = {
  padding: "0.375rem 1rem",
  fontSize: "0.6875rem",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "var(--autodoc-on-surface-variant)",
};

const resultItemStyles: React.CSSProperties = {
  display: "block",
  width: "100%",
  textAlign: "left",
  padding: "0.5rem 1rem",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  fontFamily: "inherit",
  transition: "background-color 120ms ease",
};

const resultTitleStyles: React.CSSProperties = {
  fontSize: "0.8125rem",
  fontWeight: 500,
  color: "var(--autodoc-on-surface)",
  lineHeight: 1.4,
};

const resultSnippetStyles: React.CSSProperties = {
  fontSize: "0.75rem",
  color: "var(--autodoc-on-surface-variant)",
  lineHeight: 1.4,
  marginTop: "0.125rem",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getPlaceholder(pathname: string): string {
  if (pathname.startsWith("/repos/")) {
    return "Search documentation...";
  }
  if (pathname.startsWith("/admin")) {
    return "Search...";
  }
  return "Search repositories...";
}
