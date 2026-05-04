import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useAuthMe } from "@/api/hooks";
import type { AuthUser } from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  isAdmin: boolean;
  isDeveloper: boolean;
  hasRole: (role: AuthUser["role"]) => boolean;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useAuthMe();

  const value = useMemo<AuthContextValue>(() => {
    const resolved = user ?? null;
    const role = resolved?.role;

    return {
      user: resolved,
      isLoading,
      isAdmin: role === "admin",
      isDeveloper: role === "developer" || role === "admin",
      hasRole: (r: AuthUser["role"]) => {
        if (!role) return false;
        const hierarchy: Record<AuthUser["role"], number> = {
          viewer: 0,
          developer: 1,
          admin: 2,
        };
        return hierarchy[role] >= hierarchy[r];
      },
    };
  }, [user, isLoading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// RoleGate
// ---------------------------------------------------------------------------

export function RoleGate({
  roles,
  children,
}: {
  roles: AuthUser["role"][];
  children: ReactNode;
}): ReactNode {
  const { user } = useAuth();

  if (!user || !roles.includes(user.role)) {
    return null;
  }

  return children;
}
