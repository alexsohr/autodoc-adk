import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { FilterBar } from "./FilterBar";

const meta = {
  title: "Shared/FilterBar",
  component: FilterBar,
  tags: ["autodocs"],
} satisfies Meta<typeof FilterBar>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WithCounts: Story = {
  args: {
    options: [
      { label: "All", value: "all", count: 42 },
      { label: "Healthy", value: "healthy", count: 35 },
      { label: "Running", value: "running", count: 3 },
      { label: "Failed", value: "failed", count: 2 },
      { label: "Pending", value: "pending", count: 2 },
    ],
    value: "all",
    onChange: () => {},
  },
};

export const WithoutCounts: Story = {
  args: {
    options: [
      { label: "All Repositories", value: "all" },
      { label: "Python", value: "python" },
      { label: "TypeScript", value: "typescript" },
      { label: "Go", value: "go" },
      { label: "Rust", value: "rust" },
    ],
    value: "all",
    onChange: () => {},
  },
};

export const SelectedFailed: Story = {
  args: {
    options: [
      { label: "All", value: "all", count: 42 },
      { label: "Healthy", value: "healthy", count: 35 },
      { label: "Running", value: "running", count: 3 },
      { label: "Failed", value: "failed", count: 2 },
      { label: "Pending", value: "pending", count: 2 },
    ],
    value: "failed",
    onChange: () => {},
  },
};

function InteractiveFilterBar() {
  const [value, setValue] = useState("all");
  return (
    <FilterBar
      options={[
        { label: "All Jobs", value: "all", count: 128 },
        { label: "Completed", value: "completed", count: 112 },
        { label: "Running", value: "running", count: 5 },
        { label: "Failed", value: "failed", count: 8 },
        { label: "Cancelled", value: "cancelled", count: 3 },
      ]}
      value={value}
      onChange={setValue}
    />
  );
}

export const Interactive: Story = {
  args: {
    options: [],
    value: "all",
    onChange: () => {},
  },
  render: () => <InteractiveFilterBar />,
};
