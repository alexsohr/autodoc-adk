import type { ReactNode } from "react";

export default function ChatTab(): ReactNode {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        padding: "3rem 1.5rem",
        gap: "1.5rem",
      }}
    >
      {/* Chat icon */}
      <div
        style={{
          width: "80px",
          height: "80px",
          borderRadius: "20px",
          background: "var(--autodoc-primary-fixed)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <svg
          width="40"
          height="40"
          viewBox="0 0 24 24"
          fill="none"
          style={{ color: "var(--autodoc-primary)" }}
        >
          <path
            d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM20 16H5.17L4 17.17V4H20V16Z"
            fill="currentColor"
          />
          <path d="M7 9H17V11H7V9Z" fill="currentColor" opacity="0.5" />
          <path d="M7 6H17V8H7V6Z" fill="currentColor" opacity="0.3" />
        </svg>
      </div>

      {/* Heading */}
      <h2
        style={{
          fontSize: "1.75rem",
          fontWeight: 600,
          color: "var(--autodoc-on-surface)",
          textAlign: "center",
          margin: 0,
        }}
      >
        Chat with your documentation
      </h2>

      {/* Subtitle */}
      <p
        style={{
          fontSize: "0.9375rem",
          lineHeight: 1.6,
          color: "var(--autodoc-on-surface-variant)",
          textAlign: "center",
          maxWidth: "480px",
          margin: 0,
        }}
      >
        Ask questions about your codebase and get answers powered by your generated documentation.
        Semantic search, contextual answers, and code references — all in one place.
      </p>

      {/* Coming Soon badge */}
      <span
        className="autodoc-badge autodoc-badge--info"
        style={{
          fontSize: "0.8125rem",
          padding: "0.375rem 1rem",
          fontWeight: 600,
          letterSpacing: "0.04em",
        }}
      >
        Coming Soon
      </span>

      {/* Mock chat input bar */}
      <div
        style={{
          width: "100%",
          maxWidth: "560px",
          marginTop: "1.5rem",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            background: "var(--autodoc-surface-container-high)",
            borderRadius: "12px",
            padding: "0.75rem 1rem",
            opacity: 0.5,
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style={{ color: "var(--autodoc-on-surface-variant)", flexShrink: 0 }}>
            <path
              d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z"
              fill="currentColor"
            />
          </svg>
          <span style={{ fontSize: "0.875rem", color: "var(--autodoc-on-surface-variant)" }}>
            Ask anything about your documentation...
          </span>
        </div>
      </div>
    </div>
  );
}
