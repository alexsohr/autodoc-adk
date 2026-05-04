import { NavLink } from "react-router-dom";
import { ChevronLeftIcon, ChevronRightIcon } from "@salt-ds/icons";
import { MaterialIcon } from "../shared/MaterialIcon";
import { useSidebarState } from "@/hooks/useSidebarState";
import { usePinnedRepos } from "@/hooks/usePinnedRepos";
import { RoleGate } from "@/contexts/AuthContext";

import "./Sidebar.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NavItemDef {
  to: string;
  label: string;
  icon: React.ReactNode;
  end?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Sidebar() {
  const { isCollapsed, toggle } = useSidebarState();
  const { pinnedRepoIds } = usePinnedRepos();

  const mainNav: NavItemDef[] = [
    { to: "/", label: "Repositories", icon: <MaterialIcon name="folder" size={20} />, end: true },
  ];

  const adminNav: NavItemDef[] = [
    { to: "/admin/health", label: "System Health", icon: <MaterialIcon name="monitoring" size={20} /> },
    { to: "/admin/jobs", label: "All Jobs", icon: <MaterialIcon name="work_history" size={20} /> },
    { to: "/admin/usage", label: "Usage & Costs", icon: <MaterialIcon name="bar_chart" size={20} /> },
    { to: "/admin/mcp", label: "MCP Servers", icon: <MaterialIcon name="storage" size={20} /> },
  ];

  return (
    <aside
      className={`sidebar autodoc-sidebar ${isCollapsed ? "sidebar--collapsed" : ""}`}
    >
      {/* Brand */}
      <div className="sidebar__brand">
        <div className="sidebar__brand-icon">
          <MaterialIcon name="auto_awesome" size={18} />
        </div>
        {!isCollapsed && (
          <div className="sidebar__brand-text">
            <span className="sidebar__brand-name">AutoDoc ADK</span>
            <span className="sidebar__brand-sub">Documentation Framework</span>
          </div>
        )}
      </div>

      {/* Main navigation */}
      <nav className="sidebar__nav">
        {mainNav.map((item) => (
          <SidebarItem key={item.to} item={item} collapsed={isCollapsed} />
        ))}

        {/* Pinned repos section */}
        {!isCollapsed && (
          <div className="sidebar__section">
            <span className="sidebar__section-label">Pinned Repos</span>
            {pinnedRepoIds.length === 0 && (
              <span className="sidebar__empty-hint">No pinned repos</span>
            )}
            {pinnedRepoIds.map((repoId) => (
              <NavLink
                key={repoId}
                to={`/repos/${repoId}`}
                className={({ isActive }) =>
                  `sidebar__item ${isActive ? "sidebar__item--active autodoc-sidebar-item--active" : ""}`
                }
              >
                <MaterialIcon name="push_pin" size={16} />
                <span className="sidebar__item-label">{repoId}</span>
              </NavLink>
            ))}
          </div>
        )}
        {isCollapsed && pinnedRepoIds.length > 0 && (
          <div className="sidebar__section">
            {pinnedRepoIds.map((repoId) => (
              <NavLink
                key={repoId}
                to={`/repos/${repoId}`}
                className={({ isActive }) =>
                  `sidebar__item sidebar__item--icon-only ${isActive ? "sidebar__item--active autodoc-sidebar-item--active" : ""}`
                }
                title={repoId}
              >
                <MaterialIcon name="push_pin" size={16} />
              </NavLink>
            ))}
          </div>
        )}

        {/* Admin section */}
        <RoleGate roles={["admin", "developer"]}>
          <div className="sidebar__section">
            {!isCollapsed && (
              <span className="sidebar__section-label">Admin</span>
            )}
            {adminNav.map((item) => (
              <SidebarItem key={item.to} item={item} collapsed={isCollapsed} />
            ))}
          </div>
        </RoleGate>
      </nav>

      {/* Collapse toggle */}
      <button
        className="sidebar__toggle"
        onClick={toggle}
        aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {isCollapsed ? <ChevronRightIcon size={1} /> : <ChevronLeftIcon size={1} />}
      </button>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// SidebarItem
// ---------------------------------------------------------------------------

function SidebarItem({
  item,
  collapsed,
}: {
  item: NavItemDef;
  collapsed: boolean;
}) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      data-testid={`sidebar-link-${item.label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
      className={({ isActive }) =>
        `sidebar__item ${collapsed ? "sidebar__item--icon-only" : ""} ${isActive ? "sidebar__item--active autodoc-sidebar-item--active" : ""}`
      }
      title={collapsed ? item.label : undefined}
    >
      {item.icon}
      {!collapsed && <span className="sidebar__item-label">{item.label}</span>}
    </NavLink>
  );
}
