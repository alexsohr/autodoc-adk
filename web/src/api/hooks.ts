import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  Repository,
  RepositoryOverview,
  Job,
  JobProgress,
  JobLog,
  JobTask,
  WikiStructure,
  WikiPage,
  Scope,
  SearchResponse,
  SystemHealth,
  UsageData,
  McpStatus,
  AuthUser,
  Schedule,
} from "@/types";

// ---------------------------------------------------------------------------
// Query key factories
// ---------------------------------------------------------------------------

const keys = {
  repositories: {
    all: ["repositories"] as const,
    list: (params?: { status?: string; search?: string }) =>
      ["repositories", params] as const,
    detail: (id: string) => ["repositories", id] as const,
    overview: (id: string) => ["repositories", id, "overview"] as const,
    quality: (id: string) => ["repositories", id, "quality"] as const,
    scopes: (id: string) => ["repositories", id, "scopes"] as const,
    schedule: (id: string) => ["repositories", id, "schedule"] as const,
    wikiStructure: (id: string, scopePath: string) =>
      ["repositories", id, "wiki-structure", scopePath] as const,
    wikiPage: (id: string, pageKey: string) =>
      ["repositories", id, "wiki-pages", pageKey] as const,
    pageQuality: (id: string, pageKey: string) =>
      ["repositories", id, "wiki-pages", pageKey, "quality"] as const,
    search: (
      id: string,
      params: { query: string; type?: string; scope?: string },
    ) => ["repositories", id, "search", params] as const,
  },
  jobs: {
    list: (repoId: string, params?: { status?: string }) =>
      ["jobs", repoId, params] as const,
    detail: (id: string) => ["jobs", id] as const,
    progress: (id: string) => ["jobs", id, "progress"] as const,
    tasks: (id: string) => ["jobs", id, "tasks"] as const,
    logs: (id: string) => ["jobs", id, "logs"] as const,
  },
  admin: {
    health: ["admin", "health"] as const,
    usage: (params?: { range?: string }) =>
      ["admin", "usage", params] as const,
    mcp: ["admin", "mcp"] as const,
  },
  auth: {
    me: ["auth", "me"] as const,
  },
} as const;

// ---------------------------------------------------------------------------
// Repository queries
// ---------------------------------------------------------------------------

export function useRepositories(params?: {
  status?: string;
  search?: string;
}) {
  return useQuery({
    queryKey: keys.repositories.list(params),
    queryFn: () =>
      api
        .get<{ items: Repository[] }>("/repositories", { params })
        .then((res) => res.items),
  });
}

export function useRepository(id: string) {
  return useQuery({
    queryKey: keys.repositories.detail(id),
    queryFn: () => api.get<Repository>(`/repositories/${id}`),
    enabled: !!id,
  });
}

export function useRepoOverview(id: string) {
  return useQuery({
    queryKey: keys.repositories.overview(id),
    queryFn: () =>
      api.get<RepositoryOverview>(`/repositories/${id}/overview`),
    enabled: !!id,
  });
}

export function useRepoQuality(id: string) {
  return useQuery({
    queryKey: keys.repositories.quality(id),
    queryFn: () =>
      api.get<{
        repository_id: string;
        agent_scores: { agent: string; current: number | null; previous: number | null; trend: number[] }[];
        page_scores: { page_key: string; title: string; scope: string; score: number; attempts: number; tokens: number }[];
        page_scores_total: number;
        token_breakdown: { agent: string; input_tokens: number; output_tokens: number; total_tokens: number; calls: number }[];
      }>(
        `/repositories/${id}/quality`,
      ),
    enabled: !!id,
  });
}

export function usePageQuality(repoId: string, pageKey: string) {
  return useQuery({
    queryKey: keys.repositories.pageQuality(repoId, pageKey),
    queryFn: () =>
      api.get<{
        page_key: string;
        title: string;
        scope: string;
        score: number;
        criteria_scores: Record<string, number>;
        critic_feedback: string | null;
        attempt_history: { attempt: number; score: number; passed: boolean; feedback: string | null }[];
      }>(
        `/repositories/${repoId}/quality/pages/${encodeURIComponent(pageKey)}`,
      ),
    enabled: !!repoId && !!pageKey,
  });
}

// ---------------------------------------------------------------------------
// Job queries
// ---------------------------------------------------------------------------

export function useJobs(repoId: string, params?: { status?: string }) {
  return useQuery({
    queryKey: keys.jobs.list(repoId, params),
    queryFn: () =>
      api
        .get<{ items: Job[] }>("/jobs", {
          params: { repository_id: repoId, ...params },
        })
        .then((res) => res.items),
    enabled: !!repoId,
  });
}

export function useAllJobs(params?: { status?: string }) {
  return useQuery({
    queryKey: ["jobs", "all", params],
    queryFn: async () => {
      const response = await api.get<{ items: Job[] }>("/jobs", { params });
      return response.items;
    },
  });
}

export function useJob(id: string) {
  return useQuery({
    queryKey: keys.jobs.detail(id),
    queryFn: () => api.get<Job>(`/jobs/${id}`),
    enabled: !!id,
  });
}

export function useJobProgress(id: string, enabled = true) {
  return useQuery({
    queryKey: keys.jobs.progress(id),
    queryFn: () => api.get<JobProgress>(`/jobs/${id}/progress`),
    enabled: !!id && enabled,
    refetchInterval: enabled ? 3000 : false,
  });
}

export function useJobTasks(id: string) {
  return useQuery({
    queryKey: keys.jobs.tasks(id),
    queryFn: () => api.get<JobTask[]>(`/jobs/${id}/tasks`),
    enabled: !!id,
  });
}

export function useJobLogs(id: string) {
  return useQuery({
    queryKey: keys.jobs.logs(id),
    queryFn: () => api.get<JobLog[]>(`/jobs/${id}/logs`),
    enabled: !!id,
  });
}

// ---------------------------------------------------------------------------
// Wiki / scope queries
// ---------------------------------------------------------------------------

export function useScopes(repoId: string) {
  return useQuery({
    queryKey: keys.repositories.scopes(repoId),
    queryFn: () =>
      api
        .get<{ scopes: Scope[] }>(`/documents/${repoId}/scopes`)
        .then((res) => res.scopes),
    enabled: !!repoId,
  });
}

export function useWikiStructure(repoId: string, scopePath: string) {
  return useQuery({
    queryKey: keys.repositories.wikiStructure(repoId, scopePath),
    queryFn: () =>
      api.get<WikiStructure>(
        `/documents/${repoId}/wiki`,
        { params: { scope: scopePath } },
      ),
    enabled: !!repoId && !!scopePath,
  });
}

export function useWikiPage(repoId: string, pageKey: string) {
  return useQuery({
    queryKey: keys.repositories.wikiPage(repoId, pageKey),
    queryFn: () =>
      api.get<WikiPage>(
        `/documents/${repoId}/pages/${encodeURIComponent(pageKey)}`,
      ),
    enabled: !!repoId && !!pageKey,
  });
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export function useSearch(
  repoId: string,
  params: { query: string; type?: string; scope?: string },
) {
  return useQuery({
    queryKey: keys.repositories.search(repoId, params),
    queryFn: () =>
      api.get<SearchResponse>(`/documents/${repoId}/search`, { params }),
    enabled: !!repoId && !!params.query,
  });
}

// ---------------------------------------------------------------------------
// Admin queries
// ---------------------------------------------------------------------------

export function useAdminHealth() {
  return useQuery({
    queryKey: keys.admin.health,
    queryFn: () => api.get<SystemHealth>("/admin/health"),
  });
}

export function useAdminUsage(params?: { range?: string }) {
  return useQuery({
    queryKey: keys.admin.usage(params),
    queryFn: () => api.get<UsageData>("/admin/usage", { params }),
  });
}

export function useAdminMcp() {
  return useQuery({
    queryKey: keys.admin.mcp,
    queryFn: () => api.get<McpStatus>("/admin/mcp"),
  });
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export function useAuthMe() {
  return useQuery({
    queryKey: keys.auth.me,
    queryFn: () => api.get<AuthUser>("/auth/me"),
  });
}

// ---------------------------------------------------------------------------
// Schedule
// ---------------------------------------------------------------------------

export function useRepoSchedule(repoId: string) {
  return useQuery({
    queryKey: keys.repositories.schedule(repoId),
    queryFn: () =>
      api
        .get<{ repository_id: string; schedule: Schedule }>(
          `/repositories/${repoId}/schedule`,
        )
        .then((res) => res.schedule),
    enabled: !!repoId,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateRepository() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      url: string;
      provider: "github" | "bitbucket";
      branch_mappings: Record<string, string>;
      public_branch: string;
      access_token?: string;
    }) => api.post<Repository>("/repositories", data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: keys.repositories.all,
      });
    },
  });
}

export function useUpdateRepository(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { branch_mappings?: Record<string, string>; public_branch?: string; access_token?: string }) =>
      api.patch<Repository>(`/repositories/${id}`, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: keys.repositories.all,
      });
      void queryClient.invalidateQueries({
        queryKey: keys.repositories.detail(id),
      });
      void queryClient.invalidateQueries({
        queryKey: keys.repositories.overview(id),
      });
    },
  });
}

export function useDeleteRepository(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<void>(`/repositories/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: keys.repositories.all,
      });
    },
  });
}

export function useCreateJob(repoId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      mode: Job["mode"];
      branch?: string;
    }) =>
      api.post<Job>("/jobs", {
        repository_id: repoId,
        force: data.mode === "full",
        branch: data.branch,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: keys.jobs.list(repoId),
      });
      void queryClient.invalidateQueries({
        queryKey: keys.repositories.detail(repoId),
      });
      void queryClient.invalidateQueries({
        queryKey: keys.repositories.overview(repoId),
      });
    },
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      api.post<Job>(`/jobs/${jobId}/cancel`),
    onSuccess: (_data, jobId) => {
      void queryClient.invalidateQueries({
        queryKey: keys.jobs.detail(jobId),
      });
      void queryClient.invalidateQueries({
        queryKey: keys.jobs.progress(jobId),
      });
    },
  });
}

export function useRetryJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      api.post<Job>(`/jobs/${jobId}/retry`),
    onSuccess: (_data, jobId) => {
      void queryClient.invalidateQueries({
        queryKey: keys.jobs.detail(jobId),
      });
      void queryClient.invalidateQueries({
        queryKey: keys.jobs.progress(jobId),
      });
    },
  });
}

export function useUpdateSchedule(repoId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Schedule>) =>
      api.patch<Schedule>(`/repositories/${repoId}/schedule`, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: keys.repositories.schedule(repoId),
      });
    },
  });
}

export function useCommitConfig(repoId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { message?: string }) =>
      api.post<{ commit_sha: string }>(
        `/repositories/${repoId}/config`,
        data,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: keys.repositories.detail(repoId),
      });
    },
  });
}
