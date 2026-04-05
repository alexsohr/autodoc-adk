export { api, ApiError } from "./client";
export {
  // Repository queries
  useRepositories,
  useRepository,
  useRepoOverview,
  useRepoQuality,
  usePageQuality,
  // Job queries
  useJobs,
  useJob,
  useJobProgress,
  useJobTasks,
  useJobLogs,
  // Wiki / scope queries
  useScopes,
  useWikiStructure,
  useWikiPage,
  // Search
  useSearch,
  // Admin queries
  useAdminHealth,
  useAdminUsage,
  useAdminMcp,
  // Auth
  useAuthMe,
  // Schedule
  useRepoSchedule,
  // Mutations
  useCreateRepository,
  useUpdateRepository,
  useDeleteRepository,
  useCreateJob,
  useCancelJob,
  useRetryJob,
  useUpdateSchedule,
  useCommitConfig,
} from "./hooks";
