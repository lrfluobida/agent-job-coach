"use client";

import { useState } from "react";
import Sidebar from "./Sidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      {open && <div className="sidebar-overlay" onClick={() => setOpen(false)} />}
      <div className="content">
        <div className="topbar">
          <button className="menu-button" onClick={() => setOpen(!open)}>
            菜单
          </button>
          <div style={{ fontWeight: 600, color: "var(--muted)" }}>Agent Job Coach</div>
        </div>
        <div className="main">{children}</div>
      </div>
    </div>
  );
}
