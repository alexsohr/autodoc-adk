import { type ReactNode, useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Dialog,
  DialogHeader,
  DialogContent,
  DialogActions,
  Input,
  FormField,
  FormFieldLabel,
} from "@salt-ds/core";
import {
  StatusBadge,
  FilterBar,
  SectionErrorBoundary,
} from "@/components/shared";
import { useRepositories, useCreateRepository } from "@/api/hooks";
import type { Repository } from "@/types";
import { formatRelativeTime, formatScore } from "@/utils/formatters";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAGE_SIZE = 12;

const STATUS_FILTERS = [
  { label: "All", value: "all" },
  { label: "Healthy", value: "healthy" },
  { label: "Running", value: "running" },
  { label: "Failed", value: "failed" },
  { label: "Pending", value: "pending" },
] as const;

// ---------------------------------------------------------------------------
// RepoCard
// ---------------------------------------------------------------------------

interface RepoCardProps {
  repo: Repository;
  onClick: () => void;
}

function RepoCard({ repo, onClick }: RepoCardProps): ReactNode {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        flexDirection: "column",
        background: "var(--autodoc-surface-container-lowest)",
        borderRadius: "16px",
        padding: "1.5rem",
        boxShadow: "var(--autodoc-shadow-ambient)",
        border: "none",
        cursor: "pointer",
        textAlign: "left",
        transition: "box-shadow 200ms ease-out, transform 200ms ease-out",
        minHeight: "280px",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "var(--autodoc-shadow-float)";
        e.currentTarget.style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "var(--autodoc-shadow-ambient)";
        e.currentTarget.style.transform = "translateY(0)";
      }}
    >
      {/* Header: name + status */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "8px",
              background: "var(--autodoc-surface-container)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--autodoc-primary)",
              fontSize: "1.25rem",
              flexShrink: 0,
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path
                d="M10 4H4v6h6V4zm10 0h-6v6h6V4zM10 14H4v6h6v-6zm10 0h-6v6h6v-6z"
                fill="currentColor"
                opacity="0.8"
              />
            </svg>
          </div>
          <h3
            style={{
              fontSize: "1.125rem",
              fontWeight: 700,
              color: "var(--autodoc-on-surface)",
              margin: 0,
              lineHeight: 1.3,
              wordBreak: "break-word",
            }}
          >
            {repo.name}
          </h3>
        </div>
        <StatusBadge status={repo.status ?? "pending"} />
      </div>

      {/* Description */}
      <p
        style={{
          fontSize: "0.875rem",
          color: "var(--autodoc-on-surface-variant)",
          lineHeight: 1.5,
          margin: "0 0 1.5rem",
          height: "2.625rem",
          overflow: "hidden",
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
        }}
      >
        {repo.description || "No description"}
      </p>

      {/* Running variant: progress bar */}
      {repo.status === "running" && (
        <div style={{ marginBottom: "1rem" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "0.75rem",
              color: "var(--autodoc-on-surface-variant)",
              marginBottom: "0.375rem",
            }}
          >
            <span style={{ fontWeight: 500 }}>Generating...</span>
            <span style={{ fontWeight: 600, color: "var(--autodoc-primary)" }}>In Progress</span>
          </div>
          <div
            style={{
              width: "100%",
              height: "6px",
              borderRadius: "9999px",
              background: "var(--autodoc-surface-container-high)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: "60%",
                height: "100%",
                borderRadius: "9999px",
                background: "var(--autodoc-primary)",
                animation: "autodoc-progress-indeterminate 1.5s ease-in-out infinite",
              }}
            />
          </div>
        </div>
      )}

      {/* Failed variant: error snippet */}
      {repo.status === "failed" && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.625rem 0.75rem",
            borderRadius: "8px",
            background: "var(--autodoc-error-container)",
            fontSize: "0.75rem",
            color: "var(--autodoc-on-error-container)",
            lineHeight: 1.4,
          }}
        >
          Last job failed. Click to view details.
        </div>
      )}

      {/* Metrics row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
        <div
          style={{
            background: "var(--autodoc-surface-container-low)",
            borderRadius: "12px",
            padding: "0.75rem",
          }}
        >
          <div className="autodoc-label-md" style={{ color: "var(--autodoc-outline)", marginBottom: "0.25rem", fontSize: "0.625rem" }}>
            Pages
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--autodoc-on-surface)" }}>
            {(repo.page_count ?? 0).toLocaleString()}
          </div>
        </div>
        <div
          style={{
            background: "var(--autodoc-surface-container-low)",
            borderRadius: "12px",
            padding: "0.75rem",
          }}
        >
          <div className="autodoc-label-md" style={{ color: "var(--autodoc-outline)", marginBottom: "0.25rem", fontSize: "0.625rem" }}>
            Quality
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--autodoc-primary)" }}>
            {repo.avg_quality_score != null ? formatScore(repo.avg_quality_score) : "\u2014"}
          </div>
        </div>
      </div>

      {/* Tags row */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.375rem", marginTop: "auto" }}>
        <span
          style={{
            padding: "0.25rem 0.5rem",
            borderRadius: "4px",
            background: "var(--autodoc-surface-container-high)",
            color: "var(--autodoc-on-surface-variant)",
            fontSize: "0.625rem",
            fontWeight: 500,
          }}
        >
          {repo.provider === "github" ? "GitHub" : "Bitbucket"}
        </span>
        <span
          style={{
            padding: "0.25rem 0.5rem",
            borderRadius: "4px",
            background: "var(--autodoc-surface-container-high)",
            color: "var(--autodoc-on-surface-variant)",
            fontSize: "0.625rem",
            fontWeight: 500,
          }}
        >
          {repo.scope_count ?? 0} scope{(repo.scope_count ?? 0) !== 1 ? "s" : ""}
        </span>
        {repo.last_generated_at && (
          <span
            style={{
              padding: "0.25rem 0.5rem",
              borderRadius: "4px",
              background: "var(--autodoc-surface-container-high)",
              color: "var(--autodoc-on-surface-variant)",
              fontSize: "0.625rem",
              fontWeight: 500,
            }}
          >
            {formatRelativeTime(repo.last_generated_at)}
          </span>
        )}
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// AddRepoCard
// ---------------------------------------------------------------------------

function AddRepoCard({ onClick }: { onClick: () => void }): ReactNode {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "16px",
        border: "2px dashed var(--autodoc-outline-variant)",
        background: "var(--autodoc-surface-container-low)",
        cursor: "pointer",
        minHeight: "280px",
        transition: "background-color 200ms ease-out, border-color 200ms ease-out",
        padding: "1.5rem",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--autodoc-surface-container-lowest)";
        e.currentTarget.style.borderColor = "var(--autodoc-primary)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "var(--autodoc-surface-container-low)";
        e.currentTarget.style.borderColor = "var(--autodoc-outline-variant)";
      }}
    >
      <div
        style={{
          width: "64px",
          height: "64px",
          borderRadius: "50%",
          background: "var(--autodoc-surface-container-high)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: "1rem",
          transition: "transform 200ms ease-out",
        }}
      >
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
          <path d="M12 5v14M5 12h14" stroke="var(--autodoc-primary)" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </div>
      <span style={{ fontSize: "1.125rem", fontWeight: 700, color: "var(--autodoc-on-surface)" }}>
        Add Repository
      </span>
      <span
        style={{
          fontSize: "0.875rem",
          color: "var(--autodoc-on-surface-variant)",
          marginTop: "0.5rem",
          textAlign: "center",
          maxWidth: "240px",
        }}
      >
        Connect a new source or upload local documentation files.
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// AddRepoDialog
// ---------------------------------------------------------------------------

interface AddRepoDialogProps {
  open: boolean;
  onClose: () => void;
}

function AddRepoDialog({ open, onClose }: AddRepoDialogProps): ReactNode {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [provider, setProvider] = useState<Repository["provider"]>("github");
  const [description, setDescription] = useState("");
  const [defaultBranch, setDefaultBranch] = useState("main");

  const createRepo = useCreateRepository();

  const handleSubmit = useCallback(() => {
    if (!name.trim() || !url.trim()) return;
    createRepo.mutate(
      {
        name: name.trim(),
        url: url.trim(),
        provider,
        description: description.trim() || undefined,
        default_branch: defaultBranch.trim() || "main",
      },
      {
        onSuccess: () => {
          setName("");
          setUrl("");
          setProvider("github");
          setDescription("");
          setDefaultBranch("main");
          onClose();
        },
      },
    );
  }, [name, url, provider, description, defaultBranch, createRepo, onClose]);

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen: boolean) => {
        if (!isOpen) onClose();
      }}
      style={{
        background: "rgba(255, 255, 255, var(--autodoc-glass-opacity))",
        backdropFilter: "blur(var(--autodoc-glass-blur))",
        WebkitBackdropFilter: "blur(var(--autodoc-glass-blur))",
        border: "none",
        borderRadius: "16px",
        boxShadow: "var(--autodoc-shadow-float)",
        maxWidth: "480px",
        width: "90vw",
      }}
    >
      <DialogHeader header="Add Repository" />
      <DialogContent>
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {/* Repository URL */}
          <FormField>
            <FormFieldLabel>Repository URL *</FormFieldLabel>
            <Input
              value={url}
              inputProps={{ onChange: (event) => setUrl(event.target.value) }}
              placeholder="https://github.com/org/repo"
            />
          </FormField>

          {/* Name */}
          <FormField>
            <FormFieldLabel>Name *</FormFieldLabel>
            <Input
              value={name}
              inputProps={{ onChange: (event) => setName(event.target.value) }}
              placeholder="my-project"
            />
          </FormField>

          {/* Provider */}
          <div>
            <div style={{
              display: "block",
              marginBottom: "0.375rem",
              fontSize: "0.75rem",
              fontWeight: 500,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "var(--autodoc-on-surface-variant)",
            }}>Provider</div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              {(["github", "bitbucket"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setProvider(p)}
                  style={{
                    flex: 1,
                    padding: "0.5rem",
                    borderRadius: "8px",
                    border: "none",
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    cursor: "pointer",
                    background: provider === p ? "var(--autodoc-primary)" : "var(--autodoc-surface-container)",
                    color: provider === p ? "var(--autodoc-on-primary)" : "var(--autodoc-on-surface)",
                    transition: "background-color 200ms ease-out, color 200ms ease-out",
                  }}
                >
                  {p === "github" ? "GitHub" : "Bitbucket"}
                </button>
              ))}
            </div>
          </div>

          {/* Default Branch */}
          <FormField>
            <FormFieldLabel>Default Branch</FormFieldLabel>
            <Input
              value={defaultBranch}
              inputProps={{ onChange: (event) => setDefaultBranch(event.target.value) }}
              placeholder="main"
            />
          </FormField>

          {/* Description */}
          <FormField>
            <FormFieldLabel>Description</FormFieldLabel>
            <Input
              value={description}
              inputProps={{ onChange: (event) => setDescription(event.target.value) }}
              placeholder="Optional description..."
            />
          </FormField>

          {createRepo.isError && (
            <div
              style={{
                padding: "0.625rem 0.75rem",
                borderRadius: "8px",
                background: "var(--autodoc-error-container)",
                color: "var(--autodoc-on-error-container)",
                fontSize: "0.8125rem",
              }}
            >
              {createRepo.error?.message ?? "Failed to create repository"}
            </div>
          )}
        </div>
      </DialogContent>
      <DialogActions>
        <Button appearance="transparent" onClick={onClose}>
          Cancel
        </Button>
        <Button
          appearance="solid"
          onClick={handleSubmit}
          disabled={!name.trim() || !url.trim() || createRepo.isPending}
          style={{
            background: "var(--autodoc-gradient-cta)",
            border: "none",
            color: "var(--autodoc-on-primary)",
          }}
        >
          {createRepo.isPending ? "Adding..." : "Add Repository"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// RepoListPage
// ---------------------------------------------------------------------------

export default function RepoListPage(): ReactNode {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [page, setPage] = useState(0);

  const { data: repos, isLoading, isError, error, refetch } = useRepositories();

  // Client-side filtering
  const filteredRepos = useMemo(() => {
    if (!repos) return [];
    let filtered = repos;
    if (statusFilter !== "all") {
      filtered = filtered.filter((r) => r.status === statusFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          (r.description?.toLowerCase().includes(q) ?? false),
      );
    }
    return filtered;
  }, [repos, statusFilter, searchQuery]);

  // Pagination
  const totalItems = filteredRepos.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
  const startIndex = page * PAGE_SIZE;
  const endIndex = Math.min(startIndex + PAGE_SIZE, totalItems);
  const pageItems = filteredRepos.slice(startIndex, endIndex);

  // Filter counts
  const filterOptions = useMemo(() => {
    if (!repos) return STATUS_FILTERS.map((f) => ({ ...f, count: 0 }));
    return STATUS_FILTERS.map((f) => ({
      ...f,
      count: f.value === "all" ? repos.length : repos.filter((r) => r.status === f.value).length,
    }));
  }, [repos]);

  // Reset page when filter changes
  const handleStatusChange = useCallback((value: string) => {
    setStatusFilter(value);
    setPage(0);
  }, []);

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    setPage(0);
  }, []);

  return (
    <div className="autodoc-page-padding" style={{ background: "var(--autodoc-surface-container-low)", minHeight: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "2.5rem" }}>
        <div style={{ maxWidth: "640px" }}>
          <h1 className="autodoc-display-lg" style={{ color: "var(--autodoc-on-surface)", margin: 0 }}>
            Repositories
          </h1>
          <p
            style={{
              fontSize: "1.125rem",
              color: "var(--autodoc-on-surface-variant)",
              fontWeight: 500,
              marginTop: "0.5rem",
            }}
          >
            {repos ? (
              <>
                {repos.length} repositor{repos.length !== 1 ? "ies" : "y"} registered
                <span style={{ margin: "0 0.5rem", color: "var(--autodoc-outline-variant)" }}>&bull;</span>
                <span style={{ color: "var(--autodoc-primary)" }}>All systems operational</span>
              </>
            ) : (
              "Loading..."
            )}
          </p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          style={{
            background: "var(--autodoc-gradient-cta)",
            color: "var(--autodoc-on-primary)",
            padding: "0.75rem 2rem",
            borderRadius: "12px",
            border: "none",
            fontWeight: 600,
            fontSize: "0.9375rem",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            boxShadow: "0px 4px 16px rgba(38, 77, 217, 0.2)",
            transition: "transform 200ms ease-out, opacity 200ms ease-out",
            flexShrink: 0,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.transform = "scale(1.05)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
          Add Repo
        </button>
      </div>

      {/* Filter bar + search */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.5rem",
          gap: "1rem",
          flexWrap: "wrap",
        }}
      >
        <FilterBar options={filterOptions} value={statusFilter} onChange={handleStatusChange} />
        <div style={{ position: "relative", minWidth: "240px" }}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            style={{
              position: "absolute",
              left: "0.75rem",
              top: "50%",
              transform: "translateY(-50%)",
              pointerEvents: "none",
              color: "var(--autodoc-on-surface-variant)",
            }}
          >
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="M16 16l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder="Search repositories..."
            style={{
              width: "100%",
              padding: "0.5rem 0.75rem 0.5rem 2.25rem",
              borderRadius: "9999px",
              border: "none",
              background: "var(--autodoc-surface-container-high)",
              color: "var(--autodoc-on-surface)",
              fontSize: "0.875rem",
              fontFamily: "Inter, sans-serif",
              outline: "none",
              transition: "box-shadow 200ms ease-out",
            }}
            onFocus={(e) => { e.currentTarget.style.boxShadow = "0 0 0 2px var(--autodoc-primary)"; }}
            onBlur={(e) => { e.currentTarget.style.boxShadow = "none"; }}
          />
        </div>
      </div>

      {/* Grid */}
      <SectionErrorBoundary
        isLoading={isLoading}
        isError={isError}
        error={error instanceof Error ? error : null}
        data={repos}
        onRetry={() => void refetch()}
        emptyMessage="No repositories yet. Add one to get started."
        emptyAction={{ label: "Add Repository", onClick: () => setDialogOpen(true) }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
            gap: "1.5rem",
          }}
        >
          {pageItems.map((repo) => (
            <RepoCard
              key={repo.id}
              repo={repo}
              onClick={() => navigate(`/repos/${repo.id}`)}
            />
          ))}
          <AddRepoCard onClick={() => setDialogOpen(true)} />
        </div>

        {/* Pagination footer */}
        {totalItems > 0 && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: "1.5rem",
              fontSize: "0.8125rem",
              color: "var(--autodoc-on-surface-variant)",
            }}
          >
            <span>
              Showing {startIndex + 1}&ndash;{endIndex} of {totalItems}
            </span>
            {totalPages > 1 && (
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  style={{
                    padding: "0.375rem 0.875rem",
                    borderRadius: "8px",
                    border: "none",
                    background: page === 0 ? "transparent" : "var(--autodoc-surface-container-lowest)",
                    color: page === 0 ? "var(--autodoc-outline-variant)" : "var(--autodoc-on-surface)",
                    cursor: page === 0 ? "default" : "pointer",
                    fontSize: "0.8125rem",
                    fontWeight: 500,
                    transition: "background-color 200ms ease-out",
                  }}
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  style={{
                    padding: "0.375rem 0.875rem",
                    borderRadius: "8px",
                    border: "none",
                    background: page >= totalPages - 1 ? "transparent" : "var(--autodoc-surface-container-lowest)",
                    color: page >= totalPages - 1 ? "var(--autodoc-outline-variant)" : "var(--autodoc-on-surface)",
                    cursor: page >= totalPages - 1 ? "default" : "pointer",
                    fontSize: "0.8125rem",
                    fontWeight: 500,
                    transition: "background-color 200ms ease-out",
                  }}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}
      </SectionErrorBoundary>

      {/* Add Repo Dialog */}
      <AddRepoDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />

      {/* Progress animation keyframes */}
      <style>{`
        @keyframes autodoc-progress-indeterminate {
          0% { transform: translateX(-100%); }
          50% { transform: translateX(0); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}
