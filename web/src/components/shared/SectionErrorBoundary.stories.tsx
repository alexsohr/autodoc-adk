import type { Meta, StoryObj } from "@storybook/react";
import { SectionErrorBoundary } from "./SectionErrorBoundary";

const meta = {
  title: "Shared/SectionErrorBoundary",
  component: SectionErrorBoundary,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <div style={{ maxWidth: "600px" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof SectionErrorBoundary>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Loading: Story = {
  args: {
    isLoading: true,
    isError: false,
    data: null,
    children: <div>Content that will not render</div>,
  },
};

export const ErrorWithRetry: Story = {
  args: {
    isLoading: false,
    isError: true,
    error: new Error("Failed to fetch repository list from API"),
    onRetry: () => console.log("Retrying..."),
    children: <div>Content that will not render</div>,
  },
};

export const ErrorWithoutRetry: Story = {
  args: {
    isLoading: false,
    isError: true,
    error: new Error("Permission denied: insufficient access to organization repositories"),
    children: <div>Content that will not render</div>,
  },
};

export const EmptyArray: Story = {
  args: {
    isLoading: false,
    isError: false,
    data: [],
    emptyMessage: "No repositories have been onboarded yet",
    emptyAction: { label: "Add Repository", onClick: () => console.log("Add repo") },
    children: <div>Content that will not render</div>,
  },
};

export const EmptyWithIcon: Story = {
  args: {
    isLoading: false,
    isError: false,
    data: [],
    emptyMessage: "No documentation jobs found for the selected filters",
    emptyIcon: (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <rect x="4" y="8" width="32" height="24" rx="4" stroke="currentColor" strokeWidth="2" />
        <path d="M4 16h32" stroke="currentColor" strokeWidth="2" />
        <circle cx="10" cy="12" r="1.5" fill="currentColor" />
        <circle cx="15" cy="12" r="1.5" fill="currentColor" />
        <circle cx="20" cy="12" r="1.5" fill="currentColor" />
      </svg>
    ),
    children: <div>Content that will not render</div>,
  },
};

export const NullData: Story = {
  args: {
    isLoading: false,
    isError: false,
    data: null,
    emptyMessage: "Repository details not available",
    children: <div>Content that will not render</div>,
  },
};

export const Success: Story = {
  args: {
    isLoading: false,
    isError: false,
    data: [{ id: 1, name: "autodoc-adk" }],
    children: (
      <div
        style={{
          padding: "1.5rem",
          borderRadius: "12px",
          background: "var(--autodoc-surface-container-lowest)",
          boxShadow: "var(--autodoc-shadow-ambient)",
        }}
      >
        <h3 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>Repository Content</h3>
        <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--autodoc-on-surface-variant)" }}>
          This content renders because data is present and no error occurred.
          In production, this would be a table or list of repositories.
        </p>
      </div>
    ),
  },
};
