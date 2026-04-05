import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { NotificationIcon, UserIcon } from "@salt-ds/icons";
import { ContextSearch } from "@/components/layout/ContextSearch";
import { useAuth } from "@/contexts/AuthContext";

import "./TopBar.css";

interface TopBarProps {
  sidebarCollapsed: boolean;
}

export function TopBar({ sidebarCollapsed }: TopBarProps) {
  const { user } = useAuth();
  const [notifOpen, setNotifOpen] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);

  const handleClose = useCallback(() => {
    setNotifOpen(false);
  }, []);

  useEffect(() => {
    if (!notifOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        handleClose();
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [notifOpen, handleClose]);

  return (
    <header
      className="topbar"
      style={{ left: sidebarCollapsed ? 64 : 240 }}
    >
      <Link to="/" className="topbar__logo">
        AutoDoc
      </Link>

      <div className="topbar__center">
        <ContextSearch />
      </div>

      <div className="topbar__right">
        <div ref={notifRef} style={{ position: "relative" }}>
          <button
            className="topbar__icon-btn"
            aria-label="Notifications"
            onClick={() => setNotifOpen((prev) => !prev)}
          >
            <NotificationIcon size={1} />
          </button>
          {notifOpen && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 8px)",
                right: 0,
                minWidth: 260,
                padding: "16px",
                background: "var(--autodoc-surface-raised, var(--salt-container-primary-background))",
                borderRadius: 8,
                boxShadow: "0 4px 24px rgba(0, 0, 0, 0.18)",
                zIndex: 1000,
                color: "var(--autodoc-text-primary, var(--salt-text-primary-foreground))",
                fontSize: 14,
              }}
            >
              No new notifications
            </div>
          )}
        </div>
        <div className="topbar__user">
          <UserIcon size={1} />
          {user && (
            <span className="topbar__role">{user.role}</span>
          )}
        </div>
      </div>
    </header>
  );
}
