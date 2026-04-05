import { Outlet } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { TopBar } from "@/components/layout/TopBar";
import { Sidebar } from "@/components/layout/Sidebar";
import { useSidebarState } from "@/hooks/useSidebarState";

import "./AppLayout.css";

export function AppLayout() {
  const { isCollapsed } = useSidebarState();

  return (
    <AuthProvider>
      <div className="app-layout">
        <TopBar sidebarCollapsed={isCollapsed} />
        <Sidebar />
        <main
          className="app-layout__content"
          style={{
            marginLeft: isCollapsed ? 64 : 240,
          }}
        >
          <Outlet />
        </main>
      </div>
    </AuthProvider>
  );
}
