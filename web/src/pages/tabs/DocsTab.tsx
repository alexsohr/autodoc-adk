import {
  type ReactNode,
  useState,
  useMemo,
  useEffect,
  useRef,
} from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  useScopes,
  useWikiStructure,
  useWikiPage,
} from "@/api/hooks";
import {
  ScoreBadge,
  SectionErrorBoundary,
  EmptyState,
} from "@/components/shared";
import { formatRelativeTime } from "@/utils/formatters";
import type { WikiSection, WikiStructure } from "@/types";

// ---------------------------------------------------------------------------
// Flat page list helper — used for prev/next navigation
// ---------------------------------------------------------------------------

interface FlatPage {
  pageKey: string;
  title: string;
  sectionPath: string[];
}

function flattenStructure(
  sections: WikiSection[],
  parentPath: string[] = [],
): FlatPage[] {
  const result: FlatPage[] = [];
  for (const section of sections) {
    const path = [...parentPath, section.title];
    for (const page of section.pages) {
      result.push({
        pageKey: page.page_key,
        title: page.title,
        sectionPath: path,
      });
    }
    if (section.subsections) {
      result.push(...flattenStructure(section.subsections, path));
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Importance badge
// ---------------------------------------------------------------------------

const IMPORTANCE_STYLE: Record<string, { bg: string; color: string }> = {
  critical: {
    bg: "var(--autodoc-error-container)",
    color: "var(--autodoc-on-error-container)",
  },
  high: {
    bg: "var(--autodoc-warning-bg)",
    color: "var(--autodoc-warning)",
  },
  medium: {
    bg: "var(--autodoc-info-bg)",
    color: "var(--autodoc-info)",
  },
  low: {
    bg: "var(--autodoc-surface-container-high)",
    color: "var(--autodoc-on-surface-variant)",
  },
};

function ImportanceBadge({ importance }: { importance: string }): ReactNode {
  const fallback = { bg: "var(--autodoc-surface-container-high)", color: "var(--autodoc-on-surface-variant)" };
  const resolved = IMPORTANCE_STYLE[importance] ?? fallback;
  return (
    <span
      className="autodoc-badge"
      style={{ background: resolved.bg, color: resolved.color }}
    >
      {importance}
    </span>
  );
}

// ---------------------------------------------------------------------------
// ScopeSelector
// ---------------------------------------------------------------------------

function ScopeSelector({
  repoId,
  value,
  onChange,
}: {
  repoId: string;
  value: string;
  onChange: (v: string) => void;
}): ReactNode {
  const { data: scopes, isLoading } = useScopes(repoId);

  return (
    <div
      style={{
        background: "var(--autodoc-surface-container-low)",
        padding: "1rem",
        borderRadius: "12px",
      }}
    >
      <label
        className="autodoc-label-md"
        style={{
          color: "var(--autodoc-outline)",
          display: "block",
          marginBottom: "0.5rem",
        }}
      >
        Documentation Scope
      </label>
      <select
        data-testid="docs-scope-selector"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isLoading || !scopes?.length}
        style={{
          width: "100%",
          padding: "0.625rem 0.875rem",
          borderRadius: "8px",
          border: "none",
          background: "var(--autodoc-surface-container-lowest)",
          color: "var(--autodoc-on-surface)",
          fontSize: "0.875rem",
          fontWeight: 500,
          fontFamily: "inherit",
          cursor: "pointer",
          boxShadow: "var(--autodoc-shadow-ambient)",
          transition: "box-shadow 200ms ease-out",
          appearance: "auto",
        }}
      >
        {isLoading && <option value="">Loading...</option>}
        {scopes?.map((s) => (
          <option key={s.scope_path} value={s.scope_path}>
            {s.title} ({s.page_count} pages)
          </option>
        ))}
      </select>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DocTree
// ---------------------------------------------------------------------------

function DocTreeSection({
  section,
  depth,
  activePageKey,
  repoId,
}: {
  section: WikiSection;
  depth: number;
  activePageKey: string | undefined;
  repoId: string;
}): ReactNode {
  const [expanded, setExpanded] = useState(true);
  const hasChildren =
    (section.subsections && section.subsections.length > 0) ||
    section.pages.length > 0;

  return (
    <div style={{ marginLeft: depth > 0 ? "1rem" : 0 }}>
      {/* Section header */}
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          width: "100%",
          padding: "0.375rem 0.5rem",
          borderRadius: "8px",
          border: "none",
          background: "transparent",
          cursor: hasChildren ? "pointer" : "default",
          fontSize: "0.875rem",
          fontWeight: 600,
          color: expanded
            ? "var(--autodoc-primary)"
            : "var(--autodoc-on-surface-variant)",
          fontFamily: "inherit",
          textAlign: "left",
          transition: "color 200ms ease-out, background-color 200ms ease-out",
        }}
      >
        <span
          style={{
            fontSize: "18px",
            fontFamily: "'Material Symbols Outlined'",
            fontVariationSettings: "'FILL' 0, 'wght' 400",
            transition: "transform 200ms ease-out",
            transform: expanded ? "none" : "rotate(-90deg)",
          }}
        >
          {expanded ? "folder_open" : "folder"}
        </span>
        {section.title}
      </button>

      {/* Children */}
      {expanded && (
        <div
          style={{
            marginLeft: "0.75rem",
            paddingLeft: "0.75rem",
            borderLeft: "2px solid var(--autodoc-outline-variant)",
            opacity: 0.8,
          }}
        >
          {/* Pages */}
          {section.pages.map((page) => {
            const isActive = page.page_key === activePageKey;
            return (
              <Link
                key={page.page_key}
                to={`/repos/${repoId}/docs/${encodeURIComponent(page.page_key)}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "0.375rem 0.5rem",
                  borderRadius: "8px",
                  fontSize: "0.875rem",
                  fontWeight: isActive ? 700 : 400,
                  color: isActive
                    ? "var(--autodoc-primary)"
                    : "var(--autodoc-on-surface-variant)",
                  background: isActive
                    ? "var(--autodoc-surface-container)"
                    : "transparent",
                  textDecoration: "none",
                  cursor: "pointer",
                  transition:
                    "color 200ms ease-out, background-color 200ms ease-out",
                }}
              >
                <span>{page.title}</span>
                {isActive && (
                  <span
                    style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      background: "var(--autodoc-primary)",
                      flexShrink: 0,
                    }}
                  />
                )}
              </Link>
            );
          })}

          {/* Subsections */}
          {section.subsections?.map((sub) => (
            <DocTreeSection
              key={sub.title}
              section={sub}
              depth={depth + 1}
              activePageKey={activePageKey}
              repoId={repoId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function DocTree({
  structure,
  activePageKey,
  repoId,
}: {
  structure: WikiStructure | undefined;
  activePageKey: string | undefined;
  repoId: string;
}): ReactNode {
  if (!structure || !structure.sections.length) {
    return (
      <EmptyState message="No documentation structure available for this scope." />
    );
  }

  return (
    <div data-testid="docs-tree" style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
      {structure.sections.map((section) => (
        <DocTreeSection
          key={section.title}
          section={section}
          depth={0}
          activePageKey={activePageKey}
          repoId={repoId}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DocBreadcrumb
// ---------------------------------------------------------------------------

function DocBreadcrumb({
  scopePath,
  sectionPath,
  pageTitle,
}: {
  scopePath: string;
  sectionPath: string[];
  pageTitle: string;
}): ReactNode {
  const parts = [scopePath, ...(sectionPath ?? []), pageTitle];

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.375rem",
        fontSize: "0.75rem",
        fontWeight: 500,
        color: "var(--autodoc-outline)",
        flexWrap: "wrap",
      }}
    >
      {parts.map((part, i) => {
        const isLast = i === parts.length - 1;
        return (
          <span key={i} style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
            <span
              style={{
                color: isLast
                  ? "var(--autodoc-primary)"
                  : "var(--autodoc-outline)",
                fontWeight: isLast ? 600 : 500,
              }}
            >
              {part}
            </span>
            {!isLast && (
              <span
                style={{
                  fontSize: "14px",
                  fontFamily: "'Material Symbols Outlined'",
                  fontVariationSettings: "'FILL' 0, 'wght' 400",
                }}
              >
                chevron_right
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}

// ---------------------------------------------------------------------------
// MermaidBlock
// ---------------------------------------------------------------------------

function sanitizeMermaid(raw: string): string {
  return raw.replace(/\[([^\]]*)\]/g, (_match, label: string) => {
    const cleaned = label
      .replace(/`/g, "'")
      .replace(/"/g, "#quot;");
    return `[${cleaned}]`;
  });
}

function MermaidBlock({ code }: { code: string }): ReactNode {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState(false);
  const idRef = useRef(`mermaid-${Math.random().toString(36).slice(2, 10)}`);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          fontFamily: "Inter, sans-serif",
          suppressErrorRendering: true,
        });
        const sanitized = sanitizeMermaid(code);
        const { svg: rendered } = await mermaid.render(idRef.current, sanitized);
        if (!cancelled) setSvg(rendered);
      } catch {
        if (!cancelled) setError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (error) {
    return (
      <details
        style={{
          background: "var(--autodoc-surface-container-low)",
          borderRadius: "12px",
          padding: "1rem 1.5rem",
          fontSize: "0.8125rem",
          color: "var(--autodoc-on-surface-variant)",
        }}
      >
        <summary style={{ cursor: "pointer" }}>Diagram could not be rendered</summary>
        <pre style={{ marginTop: "0.5rem", whiteSpace: "pre-wrap", fontSize: "0.75rem" }}>{code}</pre>
      </details>
    );
  }

  return (
    <div
      ref={containerRef}
      data-testid="docs-mermaid"
      style={{
        background: "var(--autodoc-surface-container-low)",
        borderRadius: "12px",
        padding: "1.5rem",
        overflow: "auto",
        display: "flex",
        justifyContent: "center",
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

// ---------------------------------------------------------------------------
// MarkdownRenderer
// ---------------------------------------------------------------------------

function MarkdownRenderer({ content }: { content: string }): ReactNode {
  return (
    <div className="autodoc-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const lang = match?.[1];
            const codeStr = String(children).replace(/\n$/, "");

            // Mermaid fenced blocks
            if (lang === "mermaid") {
              return <MermaidBlock code={codeStr} />;
            }

            // Block code
            if (lang) {
              return (
                <SyntaxHighlighter
                  style={oneLight}
                  language={lang}
                  PreTag="div"
                  customStyle={{
                    borderRadius: "12px",
                    padding: "1.5rem",
                    fontSize: "0.8125rem",
                    lineHeight: 1.7,
                    background: "var(--autodoc-surface-container-low)",
                    boxShadow: "none",
                    border: "none",
                    margin: 0,
                  }}
                >
                  {codeStr}
                </SyntaxHighlighter>
              );
            }

            // Inline code
            return (
              <code
                {...props}
                style={{
                  background: "var(--autodoc-surface-container-high)",
                  borderRadius: "4px",
                  padding: "0.125rem 0.375rem",
                  fontSize: "0.8125rem",
                  fontFamily: "monospace",
                }}
              >
                {children}
              </code>
            );
          },

          table({ children }) {
            return (
              <div style={{ overflowX: "auto", borderRadius: "12px" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontSize: "0.875rem",
                  }}
                >
                  {children}
                </table>
              </div>
            );
          },

          thead({ children }) {
            return (
              <thead
                style={{
                  background: "var(--autodoc-surface-container)",
                }}
              >
                {children}
              </thead>
            );
          },

          th({ children }) {
            return (
              <th
                style={{
                  padding: "0.625rem 1rem",
                  textAlign: "left",
                  fontSize: "0.75rem",
                  fontWeight: 500,
                  letterSpacing: "0.03em",
                  textTransform: "uppercase",
                  color: "var(--autodoc-on-surface-variant)",
                  border: "none",
                }}
              >
                {children}
              </th>
            );
          },

          td({ children }) {
            return (
              <td
                style={{
                  padding: "0.625rem 1rem",
                  color: "var(--autodoc-on-surface)",
                  border: "none",
                  background: "var(--autodoc-surface-container-low)",
                }}
              >
                {children}
              </td>
            );
          },

          tr({ children }) {
            return (
              <tr
                style={{
                  transition: "background-color 200ms ease-out",
                }}
              >
                {children}
              </tr>
            );
          },

          h1({ children }) {
            return (
              <h1
                style={{
                  fontSize: "1.75rem",
                  fontWeight: 700,
                  marginTop: "2rem",
                  marginBottom: "1rem",
                  color: "var(--autodoc-on-surface)",
                }}
              >
                {children}
              </h1>
            );
          },

          h2({ children }) {
            return (
              <h2
                style={{
                  fontSize: "1.375rem",
                  fontWeight: 600,
                  marginTop: "1.75rem",
                  marginBottom: "0.75rem",
                  color: "var(--autodoc-on-surface)",
                }}
              >
                {children}
              </h2>
            );
          },

          h3({ children }) {
            return (
              <h3
                style={{
                  fontSize: "1.125rem",
                  fontWeight: 600,
                  marginTop: "1.5rem",
                  marginBottom: "0.5rem",
                  color: "var(--autodoc-on-surface)",
                }}
              >
                {children}
              </h3>
            );
          },

          p({ children }) {
            return (
              <p
                style={{
                  fontSize: "0.9375rem",
                  lineHeight: 1.75,
                  color: "var(--autodoc-on-surface-variant)",
                  marginTop: "0.5rem",
                  marginBottom: "0.75rem",
                }}
              >
                {children}
              </p>
            );
          },

          ul({ children }) {
            return (
              <ul
                style={{
                  paddingLeft: "1.25rem",
                  lineHeight: 1.75,
                  color: "var(--autodoc-on-surface-variant)",
                  fontSize: "0.9375rem",
                }}
              >
                {children}
              </ul>
            );
          },

          ol({ children }) {
            return (
              <ol
                style={{
                  paddingLeft: "1.25rem",
                  lineHeight: 1.75,
                  color: "var(--autodoc-on-surface-variant)",
                  fontSize: "0.9375rem",
                }}
              >
                {children}
              </ol>
            );
          },

          blockquote({ children }) {
            return (
              <blockquote
                style={{
                  marginLeft: 0,
                  paddingLeft: "1rem",
                  borderLeft: "3px solid var(--autodoc-primary-fixed-dim)",
                  color: "var(--autodoc-on-surface-variant)",
                  fontStyle: "italic",
                }}
              >
                {children}
              </blockquote>
            );
          },

          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "var(--autodoc-primary)",
                  textDecoration: "none",
                  fontWeight: 500,
                }}
              >
                {children}
              </a>
            );
          },

          hr() {
            return (
              <hr
                style={{
                  border: "none",
                  height: "2px",
                  background: "var(--autodoc-surface-container-high)",
                  margin: "2rem 0",
                  borderRadius: "1px",
                }}
              />
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PageContent
// ---------------------------------------------------------------------------

function PageContent({
  repoId,
  pageKey,
  structure,
}: {
  repoId: string;
  pageKey: string;
  structure: WikiStructure | undefined;
}): ReactNode {
  const { data: page, isLoading, isError, error } = useWikiPage(repoId, pageKey);
  const navigate = useNavigate();

  const flatPages = useMemo(
    () => (structure ? flattenStructure(structure.sections) : []),
    [structure],
  );

  const currentIndex = flatPages.findIndex((p) => p.pageKey === pageKey);
  const prevPage = currentIndex > 0 ? flatPages[currentIndex - 1] : null;
  const nextPage =
    currentIndex >= 0 && currentIndex < flatPages.length - 1
      ? flatPages[currentIndex + 1]
      : null;

  return (
    <SectionErrorBoundary
      isLoading={isLoading}
      isError={isError}
      error={error instanceof Error ? error : null}
      data={page}
      emptyMessage="Select a page from the sidebar to view documentation."
    >
      {page && (
        <div
          style={{
            background: "var(--autodoc-surface-container-lowest)",
            borderRadius: "16px",
            padding: "2.5rem",
            boxShadow: "var(--autodoc-shadow-ambient)",
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          {/* Breadcrumb + Score */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "2rem",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <DocBreadcrumb
              scopePath={page.scope_path}
              sectionPath={page.section_path}
              pageTitle={page.title}
            />
            <div
              data-testid="docs-quality-pill"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                background: "var(--autodoc-surface-container)",
                padding: "0.5rem 1rem",
                borderRadius: "9999px",
              }}
            >
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "var(--autodoc-on-surface-variant)",
                }}
              >
                Quality
              </span>
              <ScoreBadge score={page.quality_score} />
            </div>
          </div>

          {/* Title */}
          <header style={{ marginBottom: "2rem" }}>
            <h2
              style={{
                fontSize: "2.25rem",
                fontWeight: 800,
                letterSpacing: "-0.02em",
                color: "var(--autodoc-on-surface)",
                margin: 0,
                lineHeight: 1.2,
              }}
            >
              {page.title}
            </h2>

            {/* Metadata bar */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "1rem",
                marginTop: "1rem",
                flexWrap: "wrap",
              }}
            >
              <ImportanceBadge importance={page.importance} />
              <span
                style={{
                  fontSize: "0.8125rem",
                  color: "var(--autodoc-on-surface-variant)",
                }}
              >
                Generated {formatRelativeTime(page.generated_at)}
              </span>
              {page.source_files.length > 0 && (
                <span
                  style={{
                    fontSize: "0.8125rem",
                    color: "var(--autodoc-primary)",
                    fontWeight: 500,
                    cursor: "default",
                  }}
                  title={page.source_files.join(", ")}
                >
                  {page.source_files.length} source file
                  {page.source_files.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>
          </header>

          {/* Markdown content */}
          <MarkdownRenderer content={page.content} />

          {/* Prev / Next navigation */}
          {(prevPage || nextPage) && (
            <div
              style={{
                marginTop: "3rem",
                paddingTop: "2rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              {prevPage ? (
                <button
                  data-testid="docs-nav-prev"
                  onClick={() =>
                    navigate(
                      `/repos/${repoId}/docs/${encodeURIComponent(prevPage.pageKey)}`,
                    )
                  }
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    gap: "0.25rem",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: "0.5rem",
                    borderRadius: "8px",
                    transition: "background-color 200ms ease-out",
                    fontFamily: "inherit",
                  }}
                >
                  <span
                    className="autodoc-label-md"
                    style={{ color: "var(--autodoc-outline)" }}
                  >
                    Previous
                  </span>
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.375rem",
                      color: "var(--autodoc-on-surface)",
                      fontWeight: 700,
                      fontSize: "0.9375rem",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "'Material Symbols Outlined'",
                        fontSize: "20px",
                        fontVariationSettings: "'FILL' 0, 'wght' 400",
                      }}
                    >
                      arrow_back
                    </span>
                    {prevPage.title}
                  </span>
                </button>
              ) : (
                <div />
              )}
              {nextPage ? (
                <button
                  data-testid="docs-nav-next"
                  onClick={() =>
                    navigate(
                      `/repos/${repoId}/docs/${encodeURIComponent(nextPage.pageKey)}`,
                    )
                  }
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                    gap: "0.25rem",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: "0.5rem",
                    borderRadius: "8px",
                    transition: "background-color 200ms ease-out",
                    fontFamily: "inherit",
                    textAlign: "right",
                  }}
                >
                  <span
                    className="autodoc-label-md"
                    style={{ color: "var(--autodoc-outline)" }}
                  >
                    Next
                  </span>
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.375rem",
                      color: "var(--autodoc-on-surface)",
                      fontWeight: 700,
                      fontSize: "0.9375rem",
                    }}
                  >
                    {nextPage.title}
                    <span
                      style={{
                        fontFamily: "'Material Symbols Outlined'",
                        fontSize: "20px",
                        fontVariationSettings: "'FILL' 0, 'wght' 400",
                      }}
                    >
                      arrow_forward
                    </span>
                  </span>
                </button>
              ) : (
                <div />
              )}
            </div>
          )}
        </div>
      )}
    </SectionErrorBoundary>
  );
}

// ---------------------------------------------------------------------------
// DocsTab (default export)
// ---------------------------------------------------------------------------

export default function DocsTab(): ReactNode {
  const { id: repoId = "", pageKey } = useParams<{
    id: string;
    pageKey: string;
  }>();

  const [scopePath, setScopePath] = useState("");
  const {
    data: scopes,
    isError: scopesError,
    refetch: refetchScopes,
  } = useScopes(repoId);

  // Auto-select first scope
  useEffect(() => {
    if (scopes && scopes.length > 0 && !scopePath) {
      const first = scopes[0];
      if (first) setScopePath(first.scope_path);
    }
  }, [scopes, scopePath]);

  const {
    data: structure,
    isLoading: structureLoading,
    isError: structureError,
    error: structureErr,
  } = useWikiStructure(repoId, scopePath);

  // Auto-navigate to first page when no page is selected
  const navigate = useNavigate();
  const flatPages = useMemo(
    () => (structure ? flattenStructure(structure.sections) : []),
    [structure],
  );

  useEffect(() => {
    if (!pageKey && flatPages.length > 0) {
      const first = flatPages[0];
      if (first) {
        navigate(
          `/repos/${repoId}/docs/${encodeURIComponent(first.pageKey)}`,
          { replace: true },
        );
      }
    }
  }, [pageKey, flatPages, repoId, navigate]);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "280px 1fr",
        gap: "1.5rem",
        minHeight: "calc(100vh - 12rem)",
      }}
    >
      {/* Sidebar */}
      <aside
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
          overflow: "auto",
          maxHeight: "calc(100vh - 12rem)",
          position: "sticky",
          top: "6rem",
          paddingRight: "0.5rem",
        }}
      >
        <ScopeSelector
          repoId={repoId}
          value={scopePath}
          onChange={setScopePath}
        />

        {/* Scopes error state */}
        {scopesError && (
          <div
            style={{
              background: "var(--autodoc-error-container)",
              borderRadius: "12px",
              padding: "1rem",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "0.75rem",
            }}
          >
            <span
              style={{
                color: "var(--autodoc-on-error-container)",
                fontWeight: 600,
                fontSize: "0.8125rem",
                textAlign: "center",
              }}
            >
              Failed to load documentation scopes
            </span>
            <button
              onClick={() => void refetchScopes()}
              style={{
                padding: "0.375rem 1rem",
                borderRadius: "8px",
                border: "none",
                background: "var(--autodoc-on-error-container)",
                color: "var(--autodoc-error-container)",
                fontWeight: 600,
                fontSize: "0.8125rem",
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              Retry
            </button>
          </div>
        )}

        <SectionErrorBoundary
          isLoading={structureLoading}
          isError={structureError}
          error={structureErr instanceof Error ? structureErr : null}
          data={structure?.sections}
          emptyMessage="No documentation scopes found. Run a documentation generation job to create scopes."
        >
          <DocTree
            structure={structure}
            activePageKey={pageKey}
            repoId={repoId}
          />
        </SectionErrorBoundary>
      </aside>

      {/* Content area */}
      <main style={{ minWidth: 0 }}>
        {pageKey ? (
          <PageContent
            repoId={repoId}
            pageKey={pageKey}
            structure={structure}
          />
        ) : (
          <div
            style={{
              background: "var(--autodoc-surface-container-lowest)",
              borderRadius: "16px",
              padding: "2.5rem",
              boxShadow: "var(--autodoc-shadow-ambient)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              minHeight: "400px",
            }}
          >
            <EmptyState message="Select a page from the documentation tree to get started." />
          </div>
        )}
      </main>
    </div>
  );
}
