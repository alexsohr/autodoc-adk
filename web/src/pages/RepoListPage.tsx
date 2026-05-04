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
  FormFieldHelperText,
  Dropdown,
  Option,
} from "@salt-ds/core";
import { ApiError } from "@/api/client";
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
      data-testid={`repo-card-${repo.name}`}
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

      {/* URL */}
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
        {repo.org}/{repo.name}
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

interface BranchMapping {
  source: string;
  wiki: string;
}

/** Parse a 422 validation error body into a map of field name to error message. */
function parseFieldErrors(error: unknown): Record<string, string> {
  const fieldErrors: Record<string, string> = {};
  if (!(error instanceof ApiError) || error.status !== 422) return fieldErrors;
  const body = error.detail as { detail?: { loc?: string[]; msg?: string }[] } | null;
  if (!body?.detail || !Array.isArray(body.detail)) return fieldErrors;
  for (const entry of body.detail) {
    if (!entry.loc || !entry.msg) continue;
    // loc is typically ["body", "field_name"] — use the last segment
    const fieldName = entry.loc[entry.loc.length - 1];
    if (fieldName) {
      fieldErrors[fieldName] = entry.msg;
    }
  }
  return fieldErrors;
}

/** Auto-detect provider from a repository URL hostname. */
function detectProvider(repoUrl: string): "github" | "bitbucket" | null {
  try {
    const hostname = new URL(repoUrl).hostname.toLowerCase();
    if (hostname.includes("github.com") || hostname.includes("github")) return "github";
    if (hostname.includes("bitbucket.org") || hostname.includes("bitbucket")) return "bitbucket";
  } catch {
    // invalid URL — ignore
  }
  return null;
}

/** Extract a repo name slug from a URL (last path segment, strip .git). */
function extractRepoName(repoUrl: string): string {
  try {
    const pathname = new URL(repoUrl).pathname;
    const segments = pathname.split("/").filter(Boolean);
    const last = segments[segments.length - 1];
    if (last) return last.replace(/\.git$/, "");
  } catch {
    // invalid URL — ignore
  }
  return "";
}

function AddRepoDialog({ open, onClose }: AddRepoDialogProps): ReactNode {
  const [url, setUrl] = useState("");
  const [provider, setProvider] = useState<"github" | "bitbucket">("github");
  const [repoNameSlug, setRepoNameSlug] = useState("");
  const [branchMappings, setBranchMappings] = useState<BranchMapping[]>([
    { source: "main", wiki: "main" },
  ]);
  const [publicBranch, setPublicBranch] = useState("main");
  const [accessToken, setAccessToken] = useState("");

  const createRepo = useCreateRepository();

  // Derive field-level errors from mutation error (Task 4.4)
  const fieldErrors = useMemo(
    () => (createRepo.isError ? parseFieldErrors(createRepo.error) : {}),
    [createRepo.isError, createRepo.error],
  );

  // Source branch keys for the public_branch dropdown
  const sourceBranches = useMemo(
    () => branchMappings.map((m) => m.source).filter(Boolean),
    [branchMappings],
  );

  // URL onChange handler (Task 4.2)
  const handleUrlChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const newUrl = event.target.value;
    setUrl(newUrl);

    // Auto-detect provider
    const detected = detectProvider(newUrl);
    if (detected) setProvider(detected);

    // Extract repo name slug
    setRepoNameSlug(extractRepoName(newUrl));
  }, []);

  // Branch mapping handlers
  const handleMappingChange = useCallback(
    (index: number, field: "source" | "wiki", value: string) => {
      setBranchMappings((prev) => {
        const updated = [...prev];
        const current = updated[index];
        if (current) {
          updated[index] = { ...current, [field]: value };
        }
        return updated;
      });
    },
    [],
  );

  const addMappingRow = useCallback(() => {
    setBranchMappings((prev) => [...prev, { source: "", wiki: "" }]);
  }, []);

  const removeMappingRow = useCallback((index: number) => {
    setBranchMappings((prev) => {
      if (prev.length <= 1) return prev; // keep at least one row
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  // Submit handler (Task 4.3)
  const handleSubmit = useCallback(() => {
    if (!url.trim()) return;
    // Convert branch mappings array to Record<string, string>
    const mappingsRecord: Record<string, string> = {};
    for (const mapping of branchMappings) {
      const src = mapping.source.trim();
      const wiki = mapping.wiki.trim();
      if (src && wiki) {
        mappingsRecord[src] = wiki;
      }
    }
    if (Object.keys(mappingsRecord).length === 0) return;

    createRepo.mutate(
      {
        url: url.trim(),
        provider,
        branch_mappings: mappingsRecord,
        public_branch: publicBranch.trim() || "main",
        ...(accessToken.trim() ? { access_token: accessToken.trim() } : {}),
      },
      {
        onSuccess: () => {
          setUrl("");
          setProvider("github");
          setRepoNameSlug("");
          setBranchMappings([{ source: "main", wiki: "main" }]);
          setPublicBranch("main");
          setAccessToken("");
          onClose();
        },
      },
    );
  }, [url, provider, branchMappings, publicBranch, accessToken, createRepo, onClose]);

  const hasValidMappings = branchMappings.some(
    (m) => m.source.trim() && m.wiki.trim(),
  );

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
        maxWidth: "560px",
        width: "90vw",
      }}
    >
      <DialogHeader header="Add Repository" />
      <DialogContent>
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {/* Repository URL */}
          <FormField validationStatus={fieldErrors["url"] ? "error" : undefined}>
            <FormFieldLabel>Repository URL *</FormFieldLabel>
            <Input
              value={url}
              inputProps={{ onChange: handleUrlChange }}
              placeholder="https://github.com/org/repo"
            />
            {fieldErrors["url"] && (
              <FormFieldHelperText>{fieldErrors["url"]}</FormFieldHelperText>
            )}
          </FormField>

          {/* Auto-extracted repo name (read-only label) */}
          {repoNameSlug && (
            <div style={{ fontSize: "0.8125rem", color: "var(--autodoc-on-surface-variant)" }}>
              Repository: <span style={{ fontWeight: 600, color: "var(--autodoc-on-surface)" }}>{repoNameSlug}</span>
            </div>
          )}

          {/* Provider (auto-detected, read-only badge) */}
          <FormField validationStatus={fieldErrors["provider"] ? "error" : undefined}>
            <FormFieldLabel>Provider</FormFieldLabel>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "0.375rem 0.75rem",
                borderRadius: "8px",
                background: "var(--autodoc-surface-container)",
                color: "var(--autodoc-on-surface)",
                fontSize: "0.875rem",
                fontWeight: 500,
                width: "fit-content",
              }}
            >
              {provider === "github" ? "GitHub" : "Bitbucket"}
              <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "var(--autodoc-on-surface-variant)" }}>
                (auto-detected)
              </span>
            </div>
            {fieldErrors["provider"] && (
              <FormFieldHelperText>{fieldErrors["provider"]}</FormFieldHelperText>
            )}
          </FormField>

          {/* Branch Mappings (key-value editor) */}
          <div>
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "0.5rem",
            }}>
              <FormFieldLabel style={{ margin: 0 }}>Branch Mappings *</FormFieldLabel>
              <button
                type="button"
                onClick={addMappingRow}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--autodoc-primary)",
                  cursor: "pointer",
                  fontSize: "0.8125rem",
                  fontWeight: 600,
                  padding: "0.25rem 0.5rem",
                  borderRadius: "6px",
                  transition: "background-color 200ms ease-out",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "var(--autodoc-surface-container)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
              >
                + Add row
              </button>
            </div>
            {/* Column headers */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 32px", gap: "0.5rem", marginBottom: "0.375rem" }}>
              <span style={{ fontSize: "0.6875rem", fontWeight: 500, color: "var(--autodoc-on-surface-variant)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Source Branch
              </span>
              <span style={{ fontSize: "0.6875rem", fontWeight: 500, color: "var(--autodoc-on-surface-variant)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Wiki Branch
              </span>
              <span />
            </div>
            {branchMappings.map((mapping, index) => (
              <div
                key={index}
                style={{ display: "grid", gridTemplateColumns: "1fr 1fr 32px", gap: "0.5rem", marginBottom: "0.5rem", alignItems: "center" }}
              >
                <Input
                  value={mapping.source}
                  inputProps={{
                    onChange: (e) => handleMappingChange(index, "source", e.target.value),
                  }}
                  placeholder="main"
                />
                <Input
                  value={mapping.wiki}
                  inputProps={{
                    onChange: (e) => handleMappingChange(index, "wiki", e.target.value),
                  }}
                  placeholder="main"
                />
                <button
                  type="button"
                  onClick={() => removeMappingRow(index)}
                  disabled={branchMappings.length <= 1}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: branchMappings.length <= 1 ? "default" : "pointer",
                    color: branchMappings.length <= 1 ? "var(--autodoc-outline-variant)" : "var(--autodoc-on-surface-variant)",
                    fontSize: "1rem",
                    padding: "0.25rem",
                    borderRadius: "4px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                  title="Remove row"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            ))}
            {fieldErrors["branch_mappings"] && (
              <div style={{ fontSize: "0.75rem", color: "var(--autodoc-error)", marginTop: "0.25rem" }}>
                {fieldErrors["branch_mappings"]}
              </div>
            )}
          </div>

          {/* Public Branch (dropdown from source branches) */}
          <FormField validationStatus={fieldErrors["public_branch"] ? "error" : undefined}>
            <FormFieldLabel>Public Branch *</FormFieldLabel>
            {sourceBranches.length > 0 ? (
              <Dropdown
                selected={[publicBranch]}
                onSelectionChange={(_event, items) => {
                  const selected = items[0];
                  if (selected) setPublicBranch(selected);
                }}
                style={{ width: "100%" }}
              >
                {sourceBranches.map((branch) => (
                  <Option key={branch} value={branch}>
                    {branch}
                  </Option>
                ))}
              </Dropdown>
            ) : (
              <Input
                value={publicBranch}
                inputProps={{ onChange: (e) => setPublicBranch(e.target.value) }}
                placeholder="main"
              />
            )}
            {fieldErrors["public_branch"] && (
              <FormFieldHelperText>{fieldErrors["public_branch"]}</FormFieldHelperText>
            )}
          </FormField>

          {/* Access Token (optional, password input) */}
          <FormField validationStatus={fieldErrors["access_token"] ? "error" : undefined}>
            <FormFieldLabel>Access Token</FormFieldLabel>
            <Input
              value={accessToken}
              inputProps={{
                onChange: (e) => setAccessToken(e.target.value),
                type: "password",
              }}
              placeholder="Optional — for private repositories"
            />
            {fieldErrors["access_token"] && (
              <FormFieldHelperText>{fieldErrors["access_token"]}</FormFieldHelperText>
            )}
          </FormField>

          {/* General error display (non-422 or non-field errors) */}
          {createRepo.isError && Object.keys(fieldErrors).length === 0 && (
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
          disabled={!url.trim() || !hasValidMappings || createRepo.isPending}
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
          r.url.toLowerCase().includes(q),
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
              Showing {startIndex + 1}-{endIndex} of {totalItems}
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
