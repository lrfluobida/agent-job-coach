"use client";

import { useState } from "react";

type IngestResponse = {
  ok: boolean;
  collection?: string;
  added?: number;
  error?: string;
};

export default function IngestPage() {
  const [sourceType, setSourceType] = useState("jd");
  const [sourceId, setSourceId] = useState("");
  const [text, setText] = useState("");
  const [resp, setResp] = useState<IngestResponse | null>(null);
  const [err, setErr] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setErr("");
    setResp(null);

    try {
      const res = await fetch("/api/ingest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          source_id: sourceId,
          source_type: sourceType,
          text,
        }),
      });

      const bodyText = await res.text();
      if (!res.ok) {
        throw new Error(bodyText || `HTTP ${res.status}`);
      }
      const json = JSON.parse(bodyText) as IngestResponse;
      setResp(json);
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <div className="page-header">
        <h1 className="page-title">导入资料</h1>
        <p className="page-subtitle">重复使用同一 source_id 会覆盖已有内容。</p>
      </div>

      <form className="panel panel-grid" onSubmit={onSubmit}>
        <div>
          <label className="label">资料类型</label>
          <select
            className="select"
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            style={{ marginTop: 8 }}
          >
            <option value="jd">岗位描述</option>
            <option value="resume">简历</option>
            <option value="notes">笔记</option>
          </select>
        </div>

        <div>
          <label className="label">source_id</label>
          <input
            className="input"
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            placeholder="例如 resume-2026-02"
            style={{ marginTop: 8 }}
            required
          />
        </div>

        <div>
          <label className="label">文本内容</label>
          <textarea
            className="textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="粘贴需要导入的完整文本..."
            style={{ marginTop: 8 }}
            required
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="button" type="submit" disabled={loading}>
            {loading ? "导入中..." : "提交"}
          </button>
          <span style={{ color: "var(--muted)", fontSize: 13 }}>将覆盖已有 source_id</span>
        </div>
      </form>

      <div className="panel-grid" style={{ marginTop: 20 }}>
        {loading && (
          <div className="panel panel-grid">
            <div className="skeleton" style={{ width: "40%" }} />
            <div className="skeleton" style={{ width: "70%" }} />
            <div className="skeleton" style={{ width: "60%" }} />
          </div>
        )}

        {resp && (
          <div className="panel">
            <div className="label">返回结果</div>
            <pre className="codeblock" style={{ marginTop: 10 }}>
              {JSON.stringify(resp, null, 2)}
            </pre>
          </div>
        )}

        {err && <div className="banner">{err}</div>}
      </div>
    </div>
  );
}
