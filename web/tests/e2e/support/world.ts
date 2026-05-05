// Shape for scenario-scoped state shared between Before/After hooks and steps.
// Extended as more domain steps are added.
export interface E2eWorld {
  currentRepoId?: string;
  currentRepoName?: string;
}
