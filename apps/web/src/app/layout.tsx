import type { Metadata } from "next";
import AppShell from "../components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Job Coach",
  description: "职业辅导 RAG 工作台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh">
      <body className="app-fonts antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
