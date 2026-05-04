import type { Meta, StoryObj } from "@storybook/react";
import { MetricCard } from "./MetricCard";

const meta = {
  title: "Shared/MetricCard",
  component: MetricCard,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <div style={{ maxWidth: "280px" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof MetricCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicCount: Story = {
  args: {
    label: "Total Repositories",
    value: 42,
  },
};

export const WithDeltaUp: Story = {
  args: {
    label: "Pages Generated",
    value: 1284,
    delta: "+73",
  },
};

export const WithDeltaDown: Story = {
  args: {
    label: "Failed Jobs",
    value: 3,
    delta: "-2",
  },
};

export const WithSubtitle: Story = {
  args: {
    label: "Average Quality Score",
    value: "8.7",
    subtitle: "Across all repositories",
  },
};

export const FullyLoaded: Story = {
  args: {
    label: "Active Pipelines",
    value: 12,
    delta: "+4",
    subtitle: "Since last deployment",
  },
};

export const Dashboard: Story = {
  args: { label: "Repositories", value: 42 },
  render: () => (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
      <MetricCard label="Repositories" value={42} delta="+3" />
      <MetricCard label="Avg Quality" value="8.7" subtitle="Last 30 days" />
      <MetricCard label="Pages Generated" value={1284} delta="+73" />
      <MetricCard label="Failed Jobs" value={3} delta="-2" />
      <MetricCard label="Active Pipelines" value={12} />
      <MetricCard label="Embedding Chunks" value="14.2k" subtitle="text-embedding-3-large" />
    </div>
  ),
};
