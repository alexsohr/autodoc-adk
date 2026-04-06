import type { Meta, StoryObj } from "@storybook/react";
import { DataTable } from "./DataTable";
import { StatusBadge } from "./StatusBadge";
import { ScoreBadge } from "./ScoreBadge";

interface RepoRow extends Record<string, unknown> {
  name: string;
  language: string;
  status: "healthy" | "running" | "failed" | "pending" | "cancelled" | "completed";
  score: number | null;
  pages: number;
  lastRun: string;
}

const sampleData: RepoRow[] = [
  { name: "autodoc-adk", language: "Python", status: "healthy", score: 9.2, pages: 47, lastRun: "2 hours ago" },
  { name: "frontend-app", language: "TypeScript", status: "running", score: 7.8, pages: 23, lastRun: "5 min ago" },
  { name: "data-pipeline", language: "Python", status: "failed", score: 5.4, pages: 12, lastRun: "1 day ago" },
  { name: "auth-service", language: "Go", status: "completed", score: 8.5, pages: 31, lastRun: "6 hours ago" },
  { name: "mobile-sdk", language: "Kotlin", status: "pending", score: null, pages: 0, lastRun: "Never" },
  { name: "infra-modules", language: "HCL", status: "healthy", score: 8.1, pages: 18, lastRun: "3 hours ago" },
  { name: "analytics-lib", language: "Python", status: "cancelled", score: 6.9, pages: 9, lastRun: "12 hours ago" },
  { name: "shared-protos", language: "Protobuf", status: "healthy", score: 9.0, pages: 15, lastRun: "1 hour ago" },
];

const columns = [
  { key: "name", header: "Repository", sortable: true, width: "200px" },
  { key: "language", header: "Language", sortable: true },
  {
    key: "status",
    header: "Status",
    render: (row: RepoRow) => <StatusBadge status={row.status} />,
  },
  {
    key: "score",
    header: "Quality",
    sortable: true,
    render: (row: RepoRow) => <ScoreBadge score={row.score} />,
  },
  { key: "pages", header: "Pages", sortable: true },
  { key: "lastRun", header: "Last Run" },
];

const meta = {
  title: "Shared/DataTable",
  component: DataTable<RepoRow>,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <div style={{ maxWidth: "900px" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof DataTable<RepoRow>>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    columns,
    data: sampleData,
  },
};

export const Sortable: Story = {
  args: {
    columns,
    data: sampleData,
    onSort: (key: string, direction: "asc" | "desc") => {
      console.log(`Sort by ${key} ${direction}`);
    },
  },
};

export const WithExpandableRows: Story = {
  args: {
    columns,
    data: sampleData,
    expandableRow: (row: RepoRow) => (
      <div style={{ fontSize: "0.875rem", color: "var(--autodoc-on-surface-variant)" }}>
        <p style={{ margin: "0 0 0.5rem" }}>
          <strong>{row.name}</strong> documentation details
        </p>
        <p style={{ margin: 0 }}>
          {row.pages} wiki pages generated with quality score {row.score ?? "N/A"}/10.
          Language: {row.language}. Last documentation run: {row.lastRun}.
        </p>
      </div>
    ),
  },
};

export const SmallPageSize: Story = {
  args: {
    columns,
    data: sampleData,
    pageSize: 3,
  },
};

export const EmptyState: Story = {
  args: {
    columns,
    data: [],
    emptyMessage: "No repositories have been onboarded yet",
  },
};

export const SingleRow: Story = {
  args: {
    columns,
    data: sampleData.slice(0, 1),
  },
};
