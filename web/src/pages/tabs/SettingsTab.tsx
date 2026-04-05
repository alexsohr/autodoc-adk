import { type ReactNode, useState, useMemo, useCallback } from "react";
import { useParams } from "react-router-dom";
import { Button, Input, MultilineInput, FormField, FormFieldLabel } from "@salt-ds/core";
import { RoleGate } from "@/contexts/AuthContext";
import {
  DataTable,
  StatusBadge,
  ConfirmDialog,
  SectionErrorBoundary,
} from "@/components/shared";
import {
  useRepository,
  useRepoSchedule,
  useUpdateRepository,
  useUpdateSchedule,
  useDeleteRepository,
} from "@/api/hooks";
import type { Schedule } from "@/types";
import { formatRelativeTime } from "@/utils/formatters";

// ---------------------------------------------------------------------------
// Sub-tab definitions
// ---------------------------------------------------------------------------

const SUB_TABS = [
  { key: "general", label: "General" },
  { key: "branches", label: "Branches" },
  { key: "webhooks", label: "Webhooks" },
  { key: "config", label: "AutoDoc Config" },
  { key: "danger", label: "Danger Zone" },
] as const;

type SubTabKey = (typeof SUB_TABS)[number]["key"];

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const sectionStyle: React.CSSProperties = {
  background: "var(--autodoc-surface-container-lowest)",
  boxShadow: "var(--autodoc-shadow-ambient)",
  borderRadius: "12px",
  padding: "1.5rem",
};

// ---------------------------------------------------------------------------
// General Settings
// ---------------------------------------------------------------------------

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] as const;

function GeneralSettings({ repoId }: { repoId: string }): ReactNode {
  const { data: repo, isLoading, isError, error, refetch } = useRepository(repoId);
  const { data: schedule } = useRepoSchedule(repoId);
  const updateSchedule = useUpdateSchedule(repoId);

  const [scheduleEnabled, setScheduleEnabled] = useState<boolean | null>(null);
  const [scheduleMode, setScheduleMode] = useState<Schedule["mode"] | null>(null);
  const [scheduleFrequency, setScheduleFrequency] = useState<Schedule["frequency"] | null>(null);
  const [scheduleDay, setScheduleDay] = useState<number | null>(null);

  // Resolve effective values (local state overrides server data)
  const effectiveEnabled = scheduleEnabled ?? schedule?.enabled ?? false;
  const effectiveMode = scheduleMode ?? schedule?.mode ?? "full";
  const effectiveFrequency = scheduleFrequency ?? schedule?.frequency ?? "weekly";
  const effectiveDay = scheduleDay ?? schedule?.day_of_week ?? 1;

  const handleSaveSchedule = useCallback(() => {
    updateSchedule.mutate({
      enabled: effectiveEnabled,
      mode: effectiveMode,
      frequency: effectiveFrequency,
      day_of_week: effectiveDay,
    });
  }, [effectiveEnabled, effectiveMode, effectiveFrequency, effectiveDay, updateSchedule]);

  return (
    <SectionErrorBoundary
      isLoading={isLoading}
      isError={isError}
      error={error as Error | null}
      data={repo}
      onRetry={() => void refetch()}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {/* Read-only info */}
        <div style={sectionStyle}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "1rem" }}>Repository Info</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <FormField>
              <FormFieldLabel>Repository URL</FormFieldLabel>
              <Input value={repo?.url ?? "\u2014"} readOnly />
            </FormField>
            <FormField>
              <FormFieldLabel>Provider</FormFieldLabel>
              <Input value={repo?.provider ?? "\u2014"} readOnly style={{ textTransform: "capitalize" }} />
            </FormField>
          </div>
        </div>

        {/* Schedule */}
        <div style={sectionStyle}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "1rem" }}>Auto-Generation Schedule</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* Enable toggle */}
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={effectiveEnabled}
                onChange={(e) => setScheduleEnabled(e.target.checked)}
                style={{ width: "18px", height: "18px", accentColor: "var(--autodoc-primary)" }}
              />
              <span style={{ fontSize: "0.875rem", fontWeight: 500 }}>Enable scheduled generation</span>
            </label>

            {effectiveEnabled && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
                <FormField>
                  <FormFieldLabel>Mode</FormFieldLabel>
                  <select
                    value={effectiveMode}
                    onChange={(e) => setScheduleMode(e.target.value as Schedule["mode"])}
                    style={{ width: "100%", padding: "0.5rem 0.75rem", borderRadius: "8px", border: "none", background: "var(--autodoc-surface-container-high)", color: "var(--autodoc-on-surface)", fontSize: "0.875rem", fontFamily: "inherit" }}
                  >
                    <option value="full">Full</option>
                    <option value="incremental">Incremental</option>
                  </select>
                </FormField>
                <FormField>
                  <FormFieldLabel>Frequency</FormFieldLabel>
                  <select
                    value={effectiveFrequency}
                    onChange={(e) => setScheduleFrequency(e.target.value as Schedule["frequency"])}
                    style={{ width: "100%", padding: "0.5rem 0.75rem", borderRadius: "8px", border: "none", background: "var(--autodoc-surface-container-high)", color: "var(--autodoc-on-surface)", fontSize: "0.875rem", fontFamily: "inherit" }}
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Biweekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </FormField>
                {(effectiveFrequency === "weekly" || effectiveFrequency === "biweekly") && (
                  <FormField>
                    <FormFieldLabel>Day</FormFieldLabel>
                    <select
                      value={effectiveDay}
                      onChange={(e) => setScheduleDay(Number(e.target.value))}
                      style={{ width: "100%", padding: "0.5rem 0.75rem", borderRadius: "8px", border: "none", background: "var(--autodoc-surface-container-high)", color: "var(--autodoc-on-surface)", fontSize: "0.875rem", fontFamily: "inherit" }}
                    >
                      {DAYS.map((day, i) => (
                        <option key={day} value={i}>
                          {day}
                        </option>
                      ))}
                    </select>
                  </FormField>
                )}
              </div>
            )}

            {schedule?.next_run_at && effectiveEnabled && (
              <div
                style={{
                  background: "var(--autodoc-info-bg)",
                  borderRadius: "8px",
                  padding: "0.625rem 1rem",
                  fontSize: "0.8125rem",
                  color: "var(--autodoc-info)",
                  fontWeight: 500,
                }}
              >
                Next run: {formatRelativeTime(schedule.next_run_at)} ({new Date(schedule.next_run_at).toLocaleDateString()})
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <Button
                appearance="solid"
                onClick={handleSaveSchedule}
                disabled={updateSchedule.isPending}
              >
                {updateSchedule.isPending ? "Saving..." : "Save Schedule"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </SectionErrorBoundary>
  );
}

// ---------------------------------------------------------------------------
// Branch Settings
// ---------------------------------------------------------------------------

interface BranchRow extends Record<string, unknown> {
  source_branch: string;
  wiki_branch: string;
}

function BranchSettings({ repoId }: { repoId: string }): ReactNode {
  const { data: repo, isLoading, isError, error, refetch } = useRepository(repoId);
  const updateRepo = useUpdateRepository(repoId);
  const [newSource, setNewSource] = useState("");
  const [newWiki, setNewWiki] = useState("");

  const branches: BranchRow[] = useMemo(
    () =>
      Object.entries(repo?.branch_mappings ?? {}).map(([source, wiki]) => ({
        source_branch: source,
        wiki_branch: wiki,
      })),
    [repo],
  );

  const handleAdd = useCallback(() => {
    if (!newSource.trim() || !newWiki.trim()) return;
    const updated = { ...(repo?.branch_mappings ?? {}), [newSource.trim()]: newWiki.trim() };
    updateRepo.mutate({ branch_mappings: updated });
    setNewSource("");
    setNewWiki("");
  }, [newSource, newWiki, repo, updateRepo]);

  const handleRemove = useCallback(
    (sourceBranch: string) => {
      const { [sourceBranch]: _, ...updated } = (repo?.branch_mappings ?? {});
      updateRepo.mutate({ branch_mappings: updated });
    },
    [repo, updateRepo],
  );

  const columns = useMemo(
    () => [
      { key: "source_branch", header: "Source Branch" },
      { key: "wiki_branch", header: "Wiki Branch" },
      {
        key: "actions",
        header: "",
        width: "80px",
        render: (row: BranchRow) => (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleRemove(row.source_branch);
            }}
            style={{
              background: "var(--autodoc-error-container)",
              color: "var(--autodoc-on-error-container)",
              border: "none",
              borderRadius: "6px",
              padding: "0.25rem 0.625rem",
              fontSize: "0.75rem",
              fontWeight: 500,
              cursor: "pointer",
              transition: "opacity 200ms ease-out",
            }}
          >
            Remove
          </button>
        ),
      },
    ],
    [handleRemove],
  );

  return (
    <SectionErrorBoundary
      isLoading={isLoading}
      isError={isError}
      error={error as Error | null}
      data={repo}
      onRetry={() => void refetch()}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <DataTable<BranchRow>
          columns={columns}
          data={branches}
          pageSize={10}
          emptyMessage="No branch mappings configured."
        />

        {/* Add new branch */}
        <div
          style={{
            ...sectionStyle,
            display: "flex",
            gap: "0.75rem",
            alignItems: "flex-end",
          }}
        >
          <FormField style={{ flex: 1 }}>
            <FormFieldLabel>Source Branch</FormFieldLabel>
            <Input
              value={newSource}
              inputProps={{ onChange: (event) => setNewSource(event.target.value) }}
              placeholder="main"
            />
          </FormField>
          <FormField style={{ flex: 1 }}>
            <FormFieldLabel>Wiki Branch</FormFieldLabel>
            <Input
              value={newWiki}
              inputProps={{ onChange: (event) => setNewWiki(event.target.value) }}
              placeholder="autodoc/main"
            />
          </FormField>
          <Button
            appearance="solid"
            onClick={handleAdd}
            disabled={!newSource.trim() || !newWiki.trim() || updateRepo.isPending}
          >
            Add
          </Button>
        </div>
      </div>
    </SectionErrorBoundary>
  );
}

// ---------------------------------------------------------------------------
// Webhook Settings
// ---------------------------------------------------------------------------

function WebhookSettings(): ReactNode {
  const [copied, setCopied] = useState<string | null>(null);

  const handleCopy = useCallback((text: string, label: string) => {
    void navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  }, []);

  // Placeholder webhook data
  const webhookUrl = "https://api.autodoc.dev/webhooks/abc123";
  const webhookSecret = "whsec_a1b2c3d4e5f6";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div style={sectionStyle}>
        <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "1rem" }}>Webhook Configuration</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <FormField>
            <FormFieldLabel>Webhook URL</FormFieldLabel>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <Input value={webhookUrl} readOnly style={{ flex: 1 }} />
              <button
                onClick={() => handleCopy(webhookUrl, "url")}
                style={{
                  padding: "0.5rem 0.75rem",
                  borderRadius: "8px",
                  border: "none",
                  background: "var(--autodoc-surface-container-high)",
                  color: "var(--autodoc-on-surface)",
                  fontSize: "0.8125rem",
                  cursor: "pointer",
                  transition: "background-color 200ms ease-out",
                  whiteSpace: "nowrap",
                }}
              >
                {copied === "url" ? "Copied" : "Copy"}
              </button>
            </div>
          </FormField>

          <FormField>
            <FormFieldLabel>Secret</FormFieldLabel>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <Input value={webhookSecret} readOnly style={{ flex: 1, fontFamily: "monospace" }} />
              <button
                onClick={() => handleCopy(webhookSecret, "secret")}
                style={{
                  padding: "0.5rem 0.75rem",
                  borderRadius: "8px",
                  border: "none",
                  background: "var(--autodoc-surface-container-high)",
                  color: "var(--autodoc-on-surface)",
                  fontSize: "0.8125rem",
                  cursor: "pointer",
                  transition: "background-color 200ms ease-out",
                  whiteSpace: "nowrap",
                }}
              >
                {copied === "secret" ? "Copied" : "Copy"}
              </button>
            </div>
          </FormField>
        </div>
      </div>

      {/* Event filters */}
      <div style={sectionStyle}>
        <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "1rem" }}>Event Filters</h3>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {["push", "pull_request", "release", "tag"].map((evt) => (
            <label key={evt} style={{ display: "flex", alignItems: "center", gap: "0.375rem", cursor: "pointer" }}>
              <input
                type="checkbox"
                defaultChecked={evt === "push" || evt === "pull_request"}
                style={{ width: "16px", height: "16px", accentColor: "var(--autodoc-primary)" }}
              />
              <span style={{ fontSize: "0.8125rem", textTransform: "capitalize" }}>{evt.replace("_", " ")}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Status + recent deliveries */}
      <div style={sectionStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Status</h3>
          <StatusBadge status="healthy" />
        </div>
        <span
          className="autodoc-label-md"
          style={{ color: "var(--autodoc-on-surface-variant)", marginBottom: "0.5rem", display: "block" }}
        >
          Recent Deliveries
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
          {[
            { event: "push", status: "completed" as const, time: "2m ago" },
            { event: "push", status: "completed" as const, time: "1h ago" },
            { event: "pull_request", status: "completed" as const, time: "3h ago" },
          ].map((d, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "0.5rem 0.75rem",
                borderRadius: "8px",
                background: "var(--autodoc-surface-container-low)",
                fontSize: "0.8125rem",
              }}
            >
              <span style={{ fontWeight: 500, textTransform: "capitalize" }}>{d.event.replace("_", " ")}</span>
              <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                <StatusBadge status={d.status} />
                <span style={{ color: "var(--autodoc-on-surface-variant)" }}>{d.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AutoDoc Config Editor
// ---------------------------------------------------------------------------

function AutoDocConfigEditor(): ReactNode {
  const defaultConfig = `# .autodoc.yaml
scopes:
  - path: "."
    name: "Root"
    description: "Project root documentation"

generation:
  model: "gemini-2.5-flash"
  quality_threshold: 7.5
  max_attempts: 3

output:
  format: "markdown"
  wiki_branch: "autodoc/main"
`;

  const [config, setConfig] = useState(defaultConfig);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div style={sectionStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>AutoDoc Configuration</h3>
          {/* TODO: Replace textarea with CodeMirror/Monaco editor for syntax highlighting */}
          <span
            className="autodoc-badge autodoc-badge--info"
            style={{ fontSize: "0.6875rem" }}
          >
            YAML
          </span>
        </div>
        <MultilineInput
          value={config}
          textAreaProps={{
            onChange: (event) => setConfig(event.target.value),
            spellCheck: false,
            style: {
              fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
              fontSize: "0.8125rem",
              lineHeight: "1.6",
              resize: "vertical",
              minHeight: "300px",
            },
          }}
          rows={16}
        />
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.75rem" }}>
          <Button appearance="transparent" onClick={() => setConfig(defaultConfig)}>
            Reset
          </Button>
          <Button appearance="solid">Save & Validate</Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Danger Zone
// ---------------------------------------------------------------------------

function DangerZone({ repoId }: { repoId: string }): ReactNode {
  const deleteRepo = useDeleteRepository(repoId);
  const [showDeleteDocs, setShowDeleteDocs] = useState(false);
  const [showUnregister, setShowUnregister] = useState(false);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div
        style={{
          background: "color-mix(in srgb, var(--autodoc-error-container) 30%, transparent)",
          borderRadius: "12px",
          padding: "1.5rem",
        }}
      >
        <h3
          style={{
            fontSize: "1rem",
            fontWeight: 600,
            color: "var(--autodoc-error)",
            marginBottom: "1rem",
          }}
        >
          Danger Zone
        </h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {/* Delete all docs */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "1rem",
              borderRadius: "8px",
              background: "color-mix(in srgb, var(--autodoc-error-container) 20%, transparent)",
            }}
          >
            <div>
              <p style={{ fontWeight: 500, fontSize: "0.875rem", margin: 0 }}>Delete all documentation</p>
              <p style={{ fontSize: "0.8125rem", color: "var(--autodoc-on-surface-variant)", margin: "0.25rem 0 0" }}>
                Remove all generated wiki pages and embeddings for this repository.
              </p>
            </div>
            <Button
              appearance="solid"
              sentiment="negative"
              onClick={() => setShowDeleteDocs(true)}
            >
              Delete Docs
            </Button>
          </div>

          {/* Unregister repo */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "1rem",
              borderRadius: "8px",
              background: "color-mix(in srgb, var(--autodoc-error-container) 20%, transparent)",
            }}
          >
            <div>
              <p style={{ fontWeight: 500, fontSize: "0.875rem", margin: 0 }}>Unregister repository</p>
              <p style={{ fontSize: "0.8125rem", color: "var(--autodoc-on-surface-variant)", margin: "0.25rem 0 0" }}>
                Permanently remove this repository and all associated data from AutoDoc.
              </p>
            </div>
            <Button
              appearance="solid"
              sentiment="negative"
              onClick={() => setShowUnregister(true)}
            >
              Unregister
            </Button>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={showDeleteDocs}
        title="Delete all documentation?"
        message="This will permanently remove all generated wiki pages and embeddings for this repository. This action cannot be undone."
        confirmLabel="Delete All Docs"
        onConfirm={() => {
          setShowDeleteDocs(false);
          // TODO: call delete docs mutation
        }}
        onCancel={() => setShowDeleteDocs(false)}
      />

      <ConfirmDialog
        open={showUnregister}
        title="Unregister repository?"
        message="This will permanently remove this repository and all associated data. All documentation, jobs, and configuration will be lost. This action cannot be undone."
        confirmLabel="Unregister"
        onConfirm={() => {
          deleteRepo.mutate();
          setShowUnregister(false);
        }}
        onCancel={() => setShowUnregister(false)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

function SettingsTabContent(): ReactNode {
  const { id: repoId } = useParams<{ id: string }>();
  const id = repoId ?? "";
  const [activeTab, setActiveTab] = useState<SubTabKey>("general");

  return (
    <div className="autodoc-page-padding" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Sub-tab navigation */}
      <nav style={{ display: "flex", gap: "0.25rem" }}>
        {SUB_TABS.map((tab) => {
          const isActive = tab.key === activeTab;
          const isDanger = tab.key === "danger";
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "8px",
                border: "none",
                fontSize: "0.8125rem",
                fontWeight: 500,
                cursor: "pointer",
                transition: "background-color 200ms ease-out, color 200ms ease-out",
                background: isActive
                  ? isDanger
                    ? "rgba(186, 26, 26, 0.1)"
                    : "var(--autodoc-primary)"
                  : "transparent",
                color: isActive
                  ? isDanger
                    ? "var(--autodoc-error)"
                    : "var(--autodoc-on-primary)"
                  : isDanger
                    ? "var(--autodoc-error)"
                    : "var(--autodoc-on-surface)",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* Tab content */}
      {activeTab === "general" && <GeneralSettings repoId={id} />}
      {activeTab === "branches" && <BranchSettings repoId={id} />}
      {activeTab === "webhooks" && <WebhookSettings />}
      {activeTab === "config" && <AutoDocConfigEditor />}
      {activeTab === "danger" && <DangerZone repoId={id} />}
    </div>
  );
}

export default function SettingsTab(): ReactNode {
  return (
    <RoleGate roles={["developer", "admin"]}>
      <SettingsTabContent />
    </RoleGate>
  );
}
