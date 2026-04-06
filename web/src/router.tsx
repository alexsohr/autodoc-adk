import { lazy, Suspense, type ReactNode } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";

// ---------------------------------------------------------------------------
// Lazy-loaded page components
// ---------------------------------------------------------------------------

const RepoListPage = lazy(() => import("@/pages/RepoListPage"));
const RepoWorkspace = lazy(() => import("@/pages/RepoWorkspace"));
const OverviewTab = lazy(() => import("@/pages/tabs/OverviewTab"));
const DocsTab = lazy(() => import("@/pages/tabs/DocsTab"));
const SearchTab = lazy(() => import("@/pages/tabs/SearchTab"));
const ChatTab = lazy(() => import("@/pages/tabs/ChatTab"));
const JobsTab = lazy(() => import("@/pages/tabs/JobsTab"));
const QualityTab = lazy(() => import("@/pages/tabs/QualityTab"));
const SettingsTab = lazy(() => import("@/pages/tabs/SettingsTab"));
const JobDetailPage = lazy(() => import("@/pages/JobDetailPage"));
const SystemHealthPage = lazy(() => import("@/pages/admin/SystemHealthPage"));
const AllJobsPage = lazy(() => import("@/pages/admin/AllJobsPage"));
const UsageCostsPage = lazy(() => import("@/pages/admin/UsageCostsPage"));
const McpServersPage = lazy(() => import("@/pages/admin/McpServersPage"));

// ---------------------------------------------------------------------------
// Suspense wrapper
// ---------------------------------------------------------------------------

function SuspenseWrapper({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            color: "var(--autodoc-on-surface-variant)",
          }}
        >
          Loading...
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

export function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        {/* Repository list */}
        <Route
          index
          element={
            <SuspenseWrapper>
              <RepoListPage />
            </SuspenseWrapper>
          }
        />

        {/* Repository workspace with nested tabs */}
        <Route
          path="repos/:id"
          element={
            <SuspenseWrapper>
              <RepoWorkspace />
            </SuspenseWrapper>
          }
        >
          <Route
            index
            element={
              <SuspenseWrapper>
                <OverviewTab />
              </SuspenseWrapper>
            }
          />
          <Route
            path="docs"
            element={
              <SuspenseWrapper>
                <DocsTab />
              </SuspenseWrapper>
            }
          />
          <Route
            path="docs/:pageKey"
            element={
              <SuspenseWrapper>
                <DocsTab />
              </SuspenseWrapper>
            }
          />
          <Route
            path="search"
            element={
              <SuspenseWrapper>
                <SearchTab />
              </SuspenseWrapper>
            }
          />
          <Route
            path="chat"
            element={
              <SuspenseWrapper>
                <ChatTab />
              </SuspenseWrapper>
            }
          />
          <Route
            path="jobs"
            element={
              <SuspenseWrapper>
                <JobsTab />
              </SuspenseWrapper>
            }
          />
          <Route
            path="jobs/:jobId"
            element={
              <SuspenseWrapper>
                <JobDetailPage />
              </SuspenseWrapper>
            }
          />
          <Route
            path="quality"
            element={
              <SuspenseWrapper>
                <QualityTab />
              </SuspenseWrapper>
            }
          />
          <Route
            path="settings"
            element={
              <SuspenseWrapper>
                <SettingsTab />
              </SuspenseWrapper>
            }
          />
        </Route>

        {/* Admin routes */}
        <Route
          path="admin/health"
          element={
            <SuspenseWrapper>
              <SystemHealthPage />
            </SuspenseWrapper>
          }
        />
        <Route
          path="admin/jobs"
          element={
            <SuspenseWrapper>
              <AllJobsPage />
            </SuspenseWrapper>
          }
        />
        <Route
          path="admin/usage"
          element={
            <SuspenseWrapper>
              <UsageCostsPage />
            </SuspenseWrapper>
          }
        />
        <Route
          path="admin/mcp"
          element={
            <SuspenseWrapper>
              <McpServersPage />
            </SuspenseWrapper>
          }
        />
      {/* Catch-all — redirect unknown routes to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
