import type { Meta, StoryObj } from "@storybook/react";
import { StatusBadge } from "./StatusBadge";

const meta = {
  title: "Shared/StatusBadge",
  component: StatusBadge,
  tags: ["autodocs"],
  argTypes: {
    status: {
      control: "select",
      options: ["healthy", "running", "failed", "pending", "cancelled", "completed"],
    },
  },
} satisfies Meta<typeof StatusBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Healthy: Story = {
  args: { status: "healthy" },
};

export const Running: Story = {
  args: { status: "running" },
};

export const Failed: Story = {
  args: { status: "failed" },
};

export const Pending: Story = {
  args: { status: "pending" },
};

export const Cancelled: Story = {
  args: { status: "cancelled" },
};

export const Completed: Story = {
  args: { status: "completed" },
};

export const AllStatuses: Story = {
  args: { status: "healthy" },
  render: () => (
    <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
      <StatusBadge status="healthy" />
      <StatusBadge status="running" />
      <StatusBadge status="failed" />
      <StatusBadge status="pending" />
      <StatusBadge status="cancelled" />
      <StatusBadge status="completed" />
    </div>
  ),
};
