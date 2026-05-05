import { type ReactNode, useState, useCallback } from "react";
import {
  MetricCard,
  StatusBadge,
  SectionErrorBoundary,
} from "@/components/shared";
import { useAdminMcp } from "@/api/hooks";

// ---------------------------------------------------------------------------
// Code snippets
// ---------------------------------------------------------------------------

const CODE_SNIPPETS = {
  vscode: {
    label: "VS Code (Continue / Copilot)",
    language: "json",
    code: `// .vscode/settings.json
{
  "mcp.servers": {
    "autodoc": {
      "url": "http://localhost:8080/mcp",
      "transport": "sse"
    }
  }
}`,
  },
  claude: {
    label: "Claude Code",
    language: "json",
    code: `// ~/.claude/claude_desktop_config.json
{
  "mcpServers": {
    "autodoc": {
      "command": "npx",
      "args": [
        "-y",
        "@anthropic/mcp-proxy",
        "http://localhost:8080/mcp"
      ]
    }
  }
}`,
  },
  generic: {
    label: "Generic MCP Client",
    language: "python",
    code: `from mcp import ClientSession
from mcp.client.sse import sse_client

async with sse_client("http://localhost:8080/mcp") as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print(tools)`,
  },
} as const;

type SnippetKey = keyof typeof CODE_SNIPPETS;

// ---------------------------------------------------------------------------
// Copy button component
// ---------------------------------------------------------------------------

function CopyButton({ text }: { text: string }): ReactNode {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      style={{
        padding: "0.375rem 0.75rem",
        borderRadius: "6px",
        border: "none",
        background: copied ? "var(--autodoc-success-bg)" : "var(--autodoc-surface-container-high)",
        color: copied ? "var(--autodoc-success)" : "var(--autodoc-on-surface)",
        fontSize: "0.75rem",
        fontWeight: 500,
        cursor: "pointer",
        transition: "background-color 200ms ease-out, color 200ms ease-out",
        whiteSpace: "nowrap",
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function McpServersPage(): ReactNode {
  const { data, isLoading, isError, error, refetch } = useAdminMcp();
  const [activeSnippet, setActiveSnippet] = useState<SnippetKey>("vscode");

  return (
    <div className="autodoc-page-padding" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div>
        <h1 className="autodoc-headline-lg" style={{ marginBottom: "0.25rem" }}>
          MCP Servers
        </h1>
        <p style={{ color: "var(--autodoc-on-surface-variant)", fontSize: "0.9375rem" }}>
          Model Context Protocol server status, usage, and integration guides
        </p>
      </div>

      <SectionErrorBoundary
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
        data={data}
        onRetry={() => void refetch()}
      >
        {/* Server status + usage cards */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
          {/* Server status card */}
          <div
            data-testid="mcp-server-status-card"
            style={{
              background: "var(--autodoc-surface-container-lowest)",
              boxShadow: "var(--autodoc-shadow-ambient)",
              borderRadius: "12px",
              padding: "1.5rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
              <h2 style={{ fontSize: "1.125rem", fontWeight: 600 }}>Server Status</h2>
              <StatusBadge status={data?.status === "running" ? "healthy" : "failed"} />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {/* Endpoint */}
              <div>
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 500,
                    letterSpacing: "0.05em",
                    textTransform: "uppercase",
                    color: "var(--autodoc-on-surface-variant)",
                    marginBottom: "0.25rem",
                    display: "block",
                  }}
                >
                  Endpoint
                </span>
                <div
                  style={{
                    display: "flex",
                    gap: "0.5rem",
                    alignItems: "center",
                  }}
                >
                  <code
                    style={{
                      flex: 1,
                      padding: "0.5rem 0.75rem",
                      borderRadius: "8px",
                      background: "var(--autodoc-surface-container-high)",
                      fontSize: "0.8125rem",
                      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                      color: "var(--autodoc-on-surface)",
                    }}
                  >
                    {data?.endpoint_url ?? "http://localhost:8080/mcp"}
                  </code>
                  <CopyButton text={data?.endpoint_url ?? "http://localhost:8080/mcp"} />
                </div>
              </div>

              {/* Tools list */}
              <div>
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 500,
                    letterSpacing: "0.05em",
                    textTransform: "uppercase",
                    color: "var(--autodoc-on-surface-variant)",
                    marginBottom: "0.5rem",
                    display: "block",
                  }}
                >
                  Available Tools ({data?.tools?.length ?? 0})
                </span>
                <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
                  {(data?.tools ?? []).map((tool) => (
                    <span
                      key={tool.name}
                      className="autodoc-badge autodoc-badge--neutral"
                      style={{ fontFamily: "monospace", fontSize: "0.75rem" }}
                      title={tool.description ?? ""}
                    >
                      {tool.name}
                    </span>
                  ))}
                  {(!data?.tools || data.tools.length === 0) && (
                    <span style={{ color: "var(--autodoc-on-surface-variant)", fontSize: "0.8125rem" }}>
                      No tools registered
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Usage stats card */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "1rem",
            }}
          >
            <MetricCard
              label="Total Calls"
              value={String(data?.total_calls ?? 0)}
              subtitle="All-time MCP tool invocations"
            />
            <MetricCard
              label="Available Tools"
              value={String(data?.tools?.length ?? 0)}
              subtitle="Registered MCP tools"
            />
            <MetricCard
              label="Server Status"
              value={data?.status === "running" ? "Running" : "Stopped"}
              subtitle={data?.endpoint_url ?? "No endpoint configured"}
            />
          </div>
        </div>
      </SectionErrorBoundary>

      {/* Agent Integration Guide */}
      <div
        style={{
          background: "var(--autodoc-surface-container-lowest)",
          boxShadow: "var(--autodoc-shadow-ambient)",
          borderRadius: "12px",
          padding: "1.5rem",
        }}
      >
        <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: "1rem" }}>
          Agent Integration Guide
        </h2>

        {/* Snippet tabs */}
        <div style={{ display: "flex", gap: "0.25rem", marginBottom: "1rem" }}>
          {(Object.entries(CODE_SNIPPETS) as [SnippetKey, (typeof CODE_SNIPPETS)[SnippetKey]][]).map(
            ([key, snippet]) => {
              const isActive = key === activeSnippet;
              return (
                <button
                  key={key}
                  data-testid={`mcp-integration-tab-${key === "claude" ? "claude-code" : key}`}
                  onClick={() => setActiveSnippet(key)}
                  style={{
                    padding: "0.5rem 1rem",
                    borderRadius: "8px",
                    border: "none",
                    fontSize: "0.8125rem",
                    fontWeight: 500,
                    cursor: "pointer",
                    transition: "background-color 200ms ease-out, color 200ms ease-out",
                    background: isActive ? "var(--autodoc-primary)" : "transparent",
                    color: isActive ? "var(--autodoc-on-primary)" : "var(--autodoc-on-surface)",
                  }}
                >
                  {snippet.label}
                </button>
              );
            },
          )}
        </div>

        {/* Code block */}
        <div style={{ position: "relative" }}>
          <div style={{ position: "absolute", top: "0.75rem", right: "0.75rem", zIndex: 1 }}>
            <CopyButton text={CODE_SNIPPETS[activeSnippet].code} />
          </div>
          <pre
            style={{
              background: "var(--autodoc-inverse-surface)",
              color: "var(--autodoc-inverse-on-surface)",
              borderRadius: "12px",
              padding: "1.25rem 1.5rem",
              fontSize: "0.8125rem",
              lineHeight: 1.6,
              fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
              overflow: "auto",
              margin: 0,
            }}
          >
            <code>{CODE_SNIPPETS[activeSnippet].code}</code>
          </pre>
        </div>
      </div>

      {/* Security Context panel */}
      <div
        style={{
          background: "var(--autodoc-surface-container-lowest)",
          boxShadow: "var(--autodoc-shadow-ambient)",
          borderRadius: "12px",
          padding: "1.5rem",
        }}
      >
        <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: "1rem" }}>
          Security Context
        </h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))",
            gap: "1rem",
          }}
        >
          {[
            {
              label: "Transport",
              value: "Server-Sent Events (SSE)",
              detail: "Supports streaming responses",
            },
            {
              label: "Authentication",
              value: "Bearer token required",
              detail: "Tokens scoped per agent identity",
            },
            {
              label: "Rate Limiting",
              value: "100 req/min per agent",
              detail: "Configurable via environment variables",
            },
            {
              label: "Data Access",
              value: "Read-only by default",
              detail: "Write tools require admin role",
            },
          ].map((item) => (
            <div
              key={item.label}
              data-testid={`mcp-security-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
              style={{
                background: "var(--autodoc-surface-container-low)",
                borderRadius: "8px",
                padding: "1rem",
              }}
            >
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 500,
                  letterSpacing: "0.05em",
                  textTransform: "uppercase",
                  color: "var(--autodoc-on-surface-variant)",
                  display: "block",
                  marginBottom: "0.25rem",
                }}
              >
                {item.label}
              </span>
              <p style={{ fontWeight: 600, fontSize: "0.875rem", margin: "0 0 0.125rem" }}>
                {item.value}
              </p>
              <p
                style={{
                  fontSize: "0.8125rem",
                  color: "var(--autodoc-on-surface-variant)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                {item.detail}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
