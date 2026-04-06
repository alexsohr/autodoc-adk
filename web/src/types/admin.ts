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

export interface UsageData {
  total_tokens: number;
  estimated_cost: number;
  daily_burn_rate: number;
  total_jobs: number;
  success_rate: number;
  top_repos: { name: string; tokens: number }[];
  usage_by_model: { model: string; tokens: number; cost: number }[];
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
