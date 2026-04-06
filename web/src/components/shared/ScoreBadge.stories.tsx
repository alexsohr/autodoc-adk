import type { Meta, StoryObj } from "@storybook/react";
import { ScoreBadge } from "./ScoreBadge";

const meta = {
  title: "Shared/ScoreBadge",
  component: ScoreBadge,
  tags: ["autodocs"],
  argTypes: {
    score: { control: { type: "number", min: 0, max: 10, step: 0.1 } },
    maxScore: { control: { type: "number", min: 1, max: 100 } },
  },
} satisfies Meta<typeof ScoreBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const HighScore: Story = {
  args: { score: 9.2, maxScore: 10 },
};

export const MediumScore: Story = {
  args: { score: 7.4, maxScore: 10 },
};

export const LowScore: Story = {
  args: { score: 5.1, maxScore: 10 },
};

export const NullScore: Story = {
  args: { score: null },
};

export const UndefinedScore: Story = {
  args: { score: undefined },
};

export const CustomMaxScore: Story = {
  args: { score: 85, maxScore: 100 },
};

export const AllScoreRanges: Story = {
  args: { score: 8.0 },
  render: () => (
    <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
      <ScoreBadge score={9.5} />
      <ScoreBadge score={8.0} />
      <ScoreBadge score={7.3} />
      <ScoreBadge score={6.1} />
      <ScoreBadge score={4.2} />
      <ScoreBadge score={null} />
    </div>
  ),
};
