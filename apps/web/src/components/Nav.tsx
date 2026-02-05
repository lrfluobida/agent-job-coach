import Link from "next/link";

const links = [
  { href: "/", label: "Home" },
  { href: "/ingest", label: "Ingest" },
  { href: "/retrieve", label: "Retrieve" },
  { href: "/chat", label: "Chat" },
];

export default function Nav() {
  return (
    <header className="nav">
      <div className="nav-inner">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="pill">Agent Job Coach</span>
          <span style={{ fontWeight: 600, fontSize: 14, color: "var(--ink-muted)" }}>
            Career-ready RAG assistant
          </span>
        </div>
        <nav className="nav-links">
          {links.map((link) => (
            <Link key={link.href} href={link.href}>
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
