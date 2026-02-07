"use client";

import { useEffect, useState } from "react";

type HealthResp = {
  ok: boolean;
  chroma_path?: string;
};

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export default function Home() {
  const [status, setStatus] = useState<"loading" | "ok" | "fail">("loading");
  const [data, setData] = useState<HealthResp | null>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    const run = async () => {
      try {
        const resp = await fetch("/api/health", { cache: "no-store" });
        const text = await resp.text();
        if (!resp.ok) throw new Error(text || `HTTP ${resp.status}`);
        const json = JSON.parse(text) as HealthResp;
        setData(json);
        setStatus(json.ok ? "ok" : "fail");
      } catch (e: unknown) {
        setStatus("fail");
        setErr(getErrorMessage(e));
      }
    };
    run();
  }, []);

  return (
    <div className="container">
      <div className="page-header">
        <h1 className="page-title">工作台总览</h1>
        <p className="page-subtitle">检查后端状态并快速进入主要功能。</p>
      </div>

      <div className="panel panel-grid">
        <div>
          <div className="label">后端状态</div>
          <div style={{ fontSize: 20, fontWeight: 700, marginTop: 8 }}>
            {status === "loading" && "加载中..."}
            {status === "ok" && "运行正常"}
            {status === "fail" && "连接失败"}
          </div>
        </div>

        {status === "loading" && (
          <div className="panel-grid">
            <div className="skeleton" style={{ width: "60%" }} />
            <div className="skeleton" style={{ width: "80%" }} />
          </div>
        )}

        {data && (
          <pre className="codeblock">{JSON.stringify(data, null, 2)}</pre>
        )}

        {err && <div className="banner">{err}</div>}
      </div>
    </div>
  );
}
