import type { Meta, StoryObj } from "@storybook/react";
import { EmptyState } from "./EmptyState";

const meta = {
  title: "Shared/EmptyState",
  component: EmptyState,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <div style={{ maxWidth: "500px" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof EmptyState>;

export default meta;
type Story = StoryObj<typeof meta>;

export const MessageOnly: Story = {
  args: {
    message: "No repositories have been onboarded yet",
  },
};

export const WithAction: Story = {
  args: {
    message: "No documentation jobs found for the selected filters",
    action: { label: "Clear Filters", onClick: () => console.log("Clearing filters") },
  },
};

export const WithIcon: Story = {
  args: {
    icon: (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <path
          d="M20 4L4 12L20 20L36 12L20 4Z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <path d="M4 20l16 8 16-8" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        <path d="M4 28l16 8 16-8" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      </svg>
    ),
    message: "No wiki pages generated for this repository. Run a documentation pipeline to get started.",
  },
};

export const WithIconAndAction: Story = {
  args: {
    icon: (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <circle cx="20" cy="20" r="16" stroke="currentColor" strokeWidth="2" />
        <path d="M20 12v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <circle cx="20" cy="26" r="1.5" fill="currentColor" />
      </svg>
    ),
    message: "No search results found. Try adjusting your query or check that embeddings have been generated.",
    action: { label: "Generate Embeddings", onClick: () => console.log("Generating embeddings") },
  },
};

export const NoRepositories: Story = {
  args: {
    icon: (
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <rect x="6" y="6" width="28" height="28" rx="4" stroke="currentColor" strokeWidth="2" />
        <path d="M14 20h12M20 14v12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
    message: "Connect your first repository to start generating documentation with AutoDoc.",
    action: { label: "Add Repository", onClick: () => console.log("Adding repository") },
  },
};
