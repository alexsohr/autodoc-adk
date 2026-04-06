import type { ReactNode } from "react";
import { formatScore } from "@/utils/formatters";

interface ScoreBadgeProps {
  score: number | null | undefined;
  maxScore?: number;
}

function getScoreClass(score: number): string {
  if (score >= 8.0) return "autodoc-badge--success";
  if (score >= 7.0) return "autodoc-badge--warning";
  return "autodoc-badge--error";
}

export function ScoreBadge({ score, maxScore = 10 }: ScoreBadgeProps): ReactNode {
  if (score == null) {
    return (
      <span className="autodoc-badge autodoc-badge--neutral">
        {"\u2014"}
      </span>
    );
  }

  const colorClass = getScoreClass(score);

  return (
    <span className={`autodoc-badge ${colorClass}`}>
      {formatScore(score)}/{maxScore}
    </span>
  );
}
