import type { Meta, StoryObj } from "@storybook/react";
import { PipelineVisualization } from "./PipelineVisualization";

const meta = {
  title: "Shared/PipelineVisualization",
  component: PipelineVisualization,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <div style={{ maxWidth: "700px", padding: "1rem 0" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof PipelineVisualization>;

export default meta;
type Story = StoryObj<typeof meta>;

export const AllCompleted: Story = {
  args: {
    stages: [
      { name: "Clone", status: "completed", duration: 4200 },
      { name: "Discover", status: "completed", duration: 1800 },
      { name: "Scan", status: "completed", duration: 12400 },
      { name: "Structure", status: "completed", duration: 8700 },
      { name: "Generate Pages", status: "completed", duration: 45200 },
      { name: "Embeddings", status: "completed", duration: 6100 },
    ],
  },
};

export const ActiveMidPipeline: Story = {
  args: {
    stages: [
      { name: "Clone", status: "completed", duration: 3800 },
      { name: "Discover", status: "completed", duration: 2100 },
      { name: "Scan", status: "active" },
      { name: "Structure", status: "pending" },
      { name: "Generate Pages", status: "pending" },
      { name: "Embeddings", status: "pending" },
    ],
  },
};

export const FailedAtStructure: Story = {
  args: {
    stages: [
      { name: "Clone", status: "completed", duration: 4000 },
      { name: "Discover", status: "completed", duration: 1500 },
      { name: "Scan", status: "completed", duration: 11200 },
      { name: "Structure", status: "failed" },
      { name: "Generate Pages", status: "pending" },
      { name: "Embeddings", status: "pending" },
    ],
  },
};

export const JustStarted: Story = {
  args: {
    stages: [
      { name: "Clone", status: "active" },
      { name: "Discover", status: "pending" },
      { name: "Scan", status: "pending" },
      { name: "Structure", status: "pending" },
      { name: "Generate Pages", status: "pending" },
      { name: "Embeddings", status: "pending" },
    ],
  },
};

export const AllPending: Story = {
  args: {
    stages: [
      { name: "Clone", status: "pending" },
      { name: "Discover", status: "pending" },
      { name: "Scan", status: "pending" },
      { name: "Structure", status: "pending" },
      { name: "Generate Pages", status: "pending" },
      { name: "Embeddings", status: "pending" },
    ],
  },
};

export const ThreeStages: Story = {
  args: {
    stages: [
      { name: "Fetch Changes", status: "completed", duration: 2100 },
      { name: "Incremental Update", status: "active" },
      { name: "Publish", status: "pending" },
    ],
  },
};
