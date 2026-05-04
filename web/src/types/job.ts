export interface Job {
  id: string;
  repository_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  mode: "full" | "incremental";
  branch: string;
  commit_sha: string | null;
  force: boolean;
  dry_run: boolean;
  quality_report: Record<string, unknown> | null;
  token_usage: Record<string, unknown> | null;
  config_warnings: string | null;
  pull_request_url: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobSummary {
  id: string;
  status: Job["status"];
  mode: Job["mode"];
  branch: string;
  commit_sha: string;
  created_at: string;
}

export interface JobProgress {
  job_id: string;
  status: string;
  stages: PipelineStage[];
  scope_progress: ScopeProgress[];
}

export interface PipelineStage {
  name: string;
  status: "completed" | "active" | "pending" | "failed";
  duration_seconds?: number;
  started_at?: string;
  completed_at?: string;
}

export interface ScopeProgress {
  scope_path: string;
  pages_completed: number;
  pages_total: number;
}

export interface JobLog {
  timestamp: string;
  level: "info" | "warning" | "error" | "debug";
  message: string;
  task?: string;
}

export interface JobTask {
  name: string;
  status: "completed" | "running" | "pending" | "failed";
  duration_seconds?: number;
  error?: string;
}
