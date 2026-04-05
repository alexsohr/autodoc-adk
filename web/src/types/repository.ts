export interface Repository {
  id: string;
  url: string;
  provider: "github" | "bitbucket";
  org: string;
  name: string;
  branch_mappings: Record<string, string>;
  public_branch: string;
  default_branch: string;
  status: "healthy" | "running" | "failed" | "pending";
  page_count: number;
  scope_count: number;
  avg_quality_score: number | null;
  last_generated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RepositoryOverview {
  repository_id: string;
  page_count: number;
  avg_quality_score: number | null;
  scope_summaries: ScopeSummary[];
  last_job: JobSummary | null;
  recent_activity: ActivityEvent[];
}

export interface ScopeSummary {
  scope_path: string;
  page_count: number;
  avg_quality_score: number | null;
  structure_summary: string;
  status: string;
}

export type ActivityEventType = "job_completed" | "job_failed" | "job_started" | "job_created";

export interface ActivityEvent {
  job_id: string;
  event: ActivityEventType;
  timestamp: string;
  branch: string;
  mode: string;
}

/** Inline import to avoid circular dependency */
export interface JobSummary {
  id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  mode: "full" | "incremental";
  branch: string;
  created_at: string;
  updated_at: string;
}
