"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const links = [
  { href: "/", label: "首页" },
  { href: "/ingest", label: "导入资料" },
  { href: "/retrieve", label: "检索调试" },
  { href: "/chat", label: "聊天" },
];

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const router = useRouter();

  const handleNewChat = () => {
    try {
      localStorage.removeItem("jobcoach_chat_state");
      window.dispatchEvent(new CustomEvent("jobcoach:new-chat"));
    } catch {
      // ignore storage errors
    }

    if (pathname !== "/chat") {
      router.push("/chat");
    }
    onClose();
  };

  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div>
        <h2>Agent Job Coach</h2>
        <p style={{ color: "var(--muted)", marginTop: 6, fontSize: 13 }}>
          职业辅导本地工作台
        </p>
      </div>

      <nav className="sidebar-nav">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`sidebar-link ${pathname === link.href ? "active" : ""}`}
            onClick={onClose}
          >
            {link.label}
          </Link>
        ))}
      </nav>

      <div className="sidebar-section">
        <div className="label">历史记录</div>
        <button type="button" className="history-item history-item-button" onClick={handleNewChat}>
          新对话
        </button>
        <div className="history-item">简历优化草案</div>
        <div className="history-item">岗位匹配建议</div>
      </div>
    </aside>
  );
}
