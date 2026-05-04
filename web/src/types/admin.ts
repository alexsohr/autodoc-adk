export interface SystemHealth {
  // Flat fields from actual API response
  api_uptime_seconds: number | null;
  api_latency_ms: number | null;
  prefect_status: string;
  prefect_pool_count: number;
  database: {
    version: string;
    pgvector_installed: boolean;
    storage_mb: string | number;
  };
  worker_pools: WorkerPool[];
}

export interface WorkerPool {
  name: string;
  type: string;
  status: string;
  concurrency_limit: number;
}

export interface TopRepoByTokens {
  repository_id: string;
  name: string;
  total_tokens: number;
}

export interface UsageByModel {
  model: string;
  total_tokens: number;
  calls: number;
}

export interface UsageData {
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  job_count: number;
  top_repos_by_tokens: TopRepoByTokens[];
  usage_by_model: UsageByModel[];
  period_start: string | null;
  period_end: string | null;
}

export interface McpTool {
  name: string;
  description: string;
}

export interface McpStatus {
  endpoint_url: string;
  status: "running" | "stopped";
  tools: McpTool[];
  total_calls: number;
}

export interface AuthUser {
  username: string;
  email: string;
  role: "viewer" | "developer" | "admin";
}
