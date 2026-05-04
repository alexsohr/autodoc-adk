import { type ReactNode, useState, useCallback, Fragment } from "react";

interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
  width?: string | number;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  pageSize?: number;
  expandableRow?: (row: T) => ReactNode;
  onSort?: (key: string, direction: "asc" | "desc") => void;
  emptyMessage?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  pageSize = 10,
  expandableRow,
  onSort,
  emptyMessage = "No data available",
}: DataTableProps<T>): ReactNode {
  const [page, setPage] = useState(0);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const totalPages = Math.max(1, Math.ceil(data.length / pageSize));
  const start = page * pageSize;
  const end = Math.min(start + pageSize, data.length);
  const pageData = data.slice(start, end);

  const handleSort = useCallback(
    (key: string) => {
      const newDir = sortKey === key && sortDir === "asc" ? "desc" : "asc";
      setSortKey(key);
      setSortDir(newDir);
      onSort?.(key, newDir);
    },
    [sortKey, sortDir, onSort],
  );

  const handleRowClick = useCallback(
    (index: number) => {
      if (!expandableRow) return;
      setExpandedIndex(expandedIndex === index ? null : index);
    },
    [expandableRow, expandedIndex],
  );

  const sortArrow = (key: string) => {
    if (sortKey !== key) return null;
    return (
      <span style={{ marginLeft: "0.25rem", fontSize: "0.75rem" }}>
        {sortDir === "asc" ? "\u25B2" : "\u25BC"}
      </span>
    );
  };

  if (data.length === 0) {
    return (
      <div
        style={{
          padding: "3rem 1.5rem",
          textAlign: "center",
          color: "var(--autodoc-on-surface-variant)",
          background: "var(--autodoc-surface-container-lowest)",
          borderRadius: "12px",
        }}
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      style={{
        background: "var(--autodoc-surface-container-lowest)",
        borderRadius: "12px",
        overflow: "hidden",
        boxShadow: "var(--autodoc-shadow-ambient)",
      }}
    >
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontFamily: "var(--salt-text-fontFamily, Inter, sans-serif)",
        }}
      >
        <thead>
          <tr style={{ background: "var(--autodoc-surface-container)" }}>
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
                style={{
                  padding: "0.75rem 1rem",
                  textAlign: "left",
                  fontSize: "0.75rem",
                  fontWeight: 500,
                  letterSpacing: "0.05em",
                  textTransform: "uppercase" as const,
                  color: "var(--autodoc-on-surface-variant)",
                  cursor: col.sortable ? "pointer" : "default",
                  userSelect: col.sortable ? "none" : undefined,
                  width: col.width,
                  transition: "background-color 200ms ease-out",
                  border: "none",
                }}
              >
                {col.header}
                {col.sortable && sortArrow(col.key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pageData.map((row, rowIndex) => {
            const globalIndex = start + rowIndex;
            const isEven = rowIndex % 2 === 0;
            const isExpanded = expandedIndex === globalIndex;

            return (
              <Fragment key={globalIndex}>
                <tr
                  onClick={() => handleRowClick(globalIndex)}
                  style={{
                    background: isEven
                      ? "var(--autodoc-surface-container-lowest)"
                      : "var(--autodoc-surface-container-low)",
                    cursor: expandableRow ? "pointer" : "default",
                    transition: "background-color 200ms ease-out",
                  }}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      style={{
                        padding: "0.75rem 1rem",
                        fontSize: "0.875rem",
                        color: "var(--autodoc-on-surface)",
                        border: "none",
                      }}
                    >
                      {col.render ? col.render(row) : String(row[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
                {isExpanded && expandableRow && (
                  <tr>
                    <td
                      colSpan={columns.length}
                      style={{
                        padding: "1rem 1.5rem",
                        background: "var(--autodoc-surface-container-low)",
                        border: "none",
                      }}
                    >
                      {expandableRow(row)}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>

      {/* Pagination footer */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0.75rem 1rem",
          background: "var(--autodoc-surface-container)",
          fontSize: "0.8125rem",
          color: "var(--autodoc-on-surface-variant)",
        }}
      >
        <span>
          Showing {start + 1}&ndash;{end} of {data.length}
        </span>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            style={{
              padding: "0.25rem 0.75rem",
              borderRadius: "6px",
              border: "none",
              background: page === 0 ? "transparent" : "var(--autodoc-surface-container-low)",
              color: page === 0 ? "var(--autodoc-outline-variant)" : "var(--autodoc-on-surface)",
              cursor: page === 0 ? "default" : "pointer",
              fontSize: "0.8125rem",
              transition: "background-color 200ms ease-out",
            }}
          >
            Previous
          </button>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            style={{
              padding: "0.25rem 0.75rem",
              borderRadius: "6px",
              border: "none",
              background: page >= totalPages - 1 ? "transparent" : "var(--autodoc-surface-container-low)",
              color: page >= totalPages - 1 ? "var(--autodoc-outline-variant)" : "var(--autodoc-on-surface)",
              cursor: page >= totalPages - 1 ? "default" : "pointer",
              fontSize: "0.8125rem",
              transition: "background-color 200ms ease-out",
            }}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
