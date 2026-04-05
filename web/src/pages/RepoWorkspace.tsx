import { type ReactNode, createContext, useContext, useMemo } from "react";
import { useParams, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useRepository, useAuthMe } from "@/api/hooks";
import { StatusBadge, SectionErrorBoundary } from "@/components/shared";
import type { Repository, AuthUser } from "@/types";

// ---------------------------------------------------------------------------
// Repo context — shares repo data across all tabs
// ---------------------------------------------------------------------------

interface RepoContextValue {
  repo: Repository;
  repoId: string;
}

const RepoContext = createContext<RepoContextValue | null>(null);

export function useRepoContext(): RepoContextValue {
  const ctx = useContext(RepoContext);
  if (!ctx) {
    throw new Error("useRepoContext must be used within RepoWorkspace");
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

interface TabDef {
  label: string;
  path: string;
  end?: boolean;
  /** If set, only these roles can see the tab */
  roles?: AuthUser["role"][];
  /** Whether to show a "coming soon" badge */
  comingSoon?: boolean;
}

const TABS: TabDef[] = [
  { label: "Overview", path: "", end: true },
  { label: "Docs", path: "docs" },
  { label: "Search", path: "search" },
  { label: "Chat", path: "chat", comingSoon: true },
  { label: "Jobs", path: "jobs" },
  { label: "Quality", path: "quality", roles: ["developer", "admin"] },
  { label: "Settings", path: "settings", roles: ["developer", "admin"] },
];

// ---------------------------------------------------------------------------
// Tab bar styles
// ---------------------------------------------------------------------------

const tabBaseStyle: React.CSSProperties = {
  padding: "0.75rem 0",
  fontSize: "0.875rem",
  fontWeight: 500,
  textDecoration: "none",
  color: "var(--autodoc-on-surface-variant)",
  borderBottom: "2px solid transparent",
  transition: "color 200ms ease-out, border-color 200ms ease-out",
  display: "inline-flex",
  alignItems: "center",
  gap: "0.375rem",
  whiteSpace: "nowrap",
};

const tabActiveStyle: React.CSSProperties = {
  ...tabBaseStyle,
  color: "var(--autodoc-primary)",
  fontWeight: 600,
  borderBottomColor: "var(--autodoc-primary)",
};

// ---------------------------------------------------------------------------
// RepoWorkspace
// ---------------------------------------------------------------------------

export default function RepoWorkspace(): ReactNode {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const repoId = id ?? "";

  const { data: repo, isLoading, isError, error, refetch } = useRepository(repoId);
  const { data: user } = useAuthMe();

  const userRole = user?.role ?? "viewer";

  // Filter tabs based on role
  const visibleTabs = useMemo(
    () => TABS.filter((tab) => !tab.roles || tab.roles.includes(userRole)),
    [userRole],
  );

  const contextValue = useMemo<RepoContextValue | null>(
    () => (repo ? { repo, repoId } : null),
    [repo, repoId],
  );

  return (
    <div
      className="autodoc-page-padding"
      style={{
        background: "var(--autodoc-surface-container-low)",
        minHeight: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <SectionErrorBoundary
        isLoading={isLoading}
        isError={isError}
        error={error instanceof Error ? error : null}
        data={repo}
        onRetry={() => void refetch()}
        emptyMessage="Repository not found"
      >
        {repo && contextValue && (
          <>
            {/* Breadcrumbs */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                fontSize: "0.875rem",
                color: "var(--autodoc-on-surface-variant)",
                marginBottom: "0.5rem",
              }}
            >
              <button
                onClick={() => navigate("/")}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--autodoc-on-surface-variant)",
                  cursor: "pointer",
                  fontSize: "0.875rem",
                  padding: 0,
                  fontFamily: "Inter, sans-serif",
                }}
              >
                Repositories
              </button>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ color: "var(--autodoc-outline-variant)" }}>
                <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span style={{ color: "var(--autodoc-on-surface)", fontWeight: 500 }}>{repo.name}</span>
            </div>

            {/* Repo header */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-end",
                marginBottom: "1.5rem",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <h2
                    style={{
                      fontSize: "1.875rem",
                      fontWeight: 700,
                      letterSpacing: "-0.01em",
                      color: "var(--autodoc-on-surface)",
                      margin: 0,
                    }}
                  >
                    {repo.name}
                  </h2>
                  <StatusBadge status={repo.status} />
                </div>
                {repo.org && (
                  <p
                    style={{
                      color: "var(--autodoc-on-surface-variant)",
                      marginTop: "0.25rem",
                      fontSize: "0.9375rem",
                    }}
                  >
                    {repo.org}/{repo.name}
                  </p>
                )}
              </div>
              <button
                onClick={() => navigate("jobs")}
                style={{
                  background: "var(--autodoc-gradient-cta)",
                  color: "var(--autodoc-on-primary)",
                  padding: "0.625rem 1.5rem",
                  borderRadius: "12px",
                  border: "none",
                  fontWeight: 600,
                  fontSize: "0.875rem",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  boxShadow: "0px 4px 16px rgba(38, 77, 217, 0.2)",
                  transition: "transform 200ms ease-out",
                  flexShrink: 0,
                }}
                onMouseEnter={(e) => { e.currentTarget.style.transform = "scale(1.05)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M8 5v14l11-7z" fill="currentColor" />
                </svg>
                Run Full Generation
              </button>
            </div>

            {/* Tab bar */}
            <nav
              style={{
                display: "flex",
                gap: "2rem",
                marginBottom: "2rem",
                borderBottom: "1px solid rgba(196, 197, 215, 0.1)",
              }}
            >
              {visibleTabs.map((tab) => (
                <NavLink
                  key={tab.path}
                  to={tab.path}
                  end={tab.end}
                  style={({ isActive }) => (isActive ? tabActiveStyle : tabBaseStyle)}
                >
                  {tab.label}
                  {tab.comingSoon && (
                    <span
                      style={{
                        fontSize: "0.625rem",
                        fontWeight: 600,
                        letterSpacing: "0.03em",
                        padding: "0.125rem 0.375rem",
                        borderRadius: "9999px",
                        background: "var(--autodoc-surface-container-high)",
                        color: "var(--autodoc-on-surface-variant)",
                      }}
                    >
                      Coming Soon
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>

            {/* Tab content */}
            <RepoContext.Provider value={contextValue}>
              <div style={{ flex: 1 }}>
                <Outlet />
              </div>
            </RepoContext.Provider>
          </>
        )}
      </SectionErrorBoundary>
    </div>
  );
}
