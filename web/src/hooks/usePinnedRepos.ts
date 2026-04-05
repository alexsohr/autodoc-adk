import { useCallback, useMemo } from "react";
import { useLocalStorage } from "@/hooks/useLocalStorage";

export function usePinnedRepos(): {
  pinnedRepoIds: string[];
  pinRepo: (id: string) => void;
  unpinRepo: (id: string) => void;
  isPinned: (id: string) => boolean;
} {
  const [pinnedRepoIds, setPinnedRepoIds] = useLocalStorage<string[]>(
    "pinned-repos",
    [],
  );

  const pinRepo = useCallback(
    (id: string) => {
      setPinnedRepoIds((prev) =>
        prev.includes(id) ? prev : [...prev, id],
      );
    },
    [setPinnedRepoIds],
  );

  const unpinRepo = useCallback(
    (id: string) => {
      setPinnedRepoIds((prev) => prev.filter((repoId) => repoId !== id));
    },
    [setPinnedRepoIds],
  );

  const pinnedSet = useMemo(() => new Set(pinnedRepoIds), [pinnedRepoIds]);

  const isPinned = useCallback(
    (id: string) => pinnedSet.has(id),
    [pinnedSet],
  );

  return { pinnedRepoIds, pinRepo, unpinRepo, isPinned };
}
