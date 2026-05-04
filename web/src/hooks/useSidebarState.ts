import { useCallback } from "react";
import { useLocalStorage } from "@/hooks/useLocalStorage";

export function useSidebarState(): {
  isCollapsed: boolean;
  toggle: () => void;
  setCollapsed: (collapsed: boolean) => void;
} {
  const [isCollapsed, setIsCollapsed] = useLocalStorage<boolean>(
    "sidebar-collapsed",
    false,
  );

  const toggle = useCallback(() => {
    setIsCollapsed((prev) => !prev);
  }, [setIsCollapsed]);

  const setCollapsed = useCallback(
    (collapsed: boolean) => {
      setIsCollapsed(collapsed);
    },
    [setIsCollapsed],
  );

  return { isCollapsed, toggle, setCollapsed };
}
