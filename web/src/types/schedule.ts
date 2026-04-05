export interface Schedule {
  enabled: boolean;
  mode: "full" | "incremental";
  frequency: "daily" | "weekly" | "biweekly" | "monthly";
  day_of_week?: number; // 0=Sunday
  next_run_at?: string;
}
