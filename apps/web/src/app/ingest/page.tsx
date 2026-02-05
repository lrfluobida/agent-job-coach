"use client";

import { useEffect, useRef, useState } from "react";

type IngestResponse = {
  ok: boolean;
  collection?: string;
  added?: number;
  source_id?: string;
  error?: string;
};

export default function IngestPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [sourceType, setSourceType] = useState("jd");
  const [text, setText] = useState("");
  const [resp, setResp] = useState<IngestResponse | null>(null);
  const [err, setErr] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const hydratedRef = useRef(false);
  const stateRef = useRef({
    sourceType: "jd",
    text: "",
    uploadStatus: "",
    resp: null as IngestResponse | null,
    err: "",
  });

  useEffect(() => {
    try {
      const saved = localStorage.getItem("jobcoach_ingest_state");
      if (!saved) return;
      const data = JSON.parse(saved) as {
        sourceType?: string;
        text?: string;
        uploadStatus?: string;
        resp?: IngestResponse | null;
        err?: string;
      };
      if (typeof data.sourceType === "string") setSourceType(data.sourceType);
      if (typeof data.text === "string") setText(data.text);
      if (typeof data.uploadStatus === "string") setUploadStatus(data.uploadStatus);
      if (data.resp) setResp(data.resp);
      if (typeof data.err === "string") setErr(data.err);
    } catch {
      // ignore corrupted cache
    } finally {
      hydratedRef.current = true;
    }
  }, []);

  useEffect(() => {
    if (!hydratedRef.current) return;
    try {
      const snapshot = {
        sourceType,
        text,
        uploadStatus,
        resp,
        err,
      };
      stateRef.current = snapshot;
      localStorage.setItem("jobcoach_ingest_state", JSON.stringify(snapshot));
    } catch {
      // ignore storage errors
    }
  }, [sourceType, text, uploadStatus, resp, err]);

  useEffect(() => {
    return () => {
      try {
        localStorage.setItem("jobcoach_ingest_state", JSON.stringify(stateRef.current));
      } catch {
        // ignore storage errors
      }
    };
  }, []);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setErr("");
    setResp(null);
    setUploadStatus("");

    try {
      const file = fileInputRef.current?.files?.[0];
      if (file) {
        setUploading(true);
        const form = new FormData();
        form.append("file", file);
        form.append("source_type", sourceType);
        const res = await fetch("/api/ingest/file", {
          method: "POST",
          body: form,
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail ?? "上传失败");
        }
        if (data?.source_id) {
          localStorage.setItem("jobcoach_last_source_id", data.source_id);
        }
        setUploadStatus(`已入库：${data.source_id}（${data.chunks} 段）`);
        setResp({ ok: true, collection: "job_coach", added: data.chunks ?? 0 });
        return;
      }

      if (!text.trim()) {
        throw new Error("请先选择文件或填写文本内容。");
      }

      const res = await fetch("/api/ingest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
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
      setUploading(false);
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
          <label className="label">文件（可选）</label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.pdf,.docx"
            style={{ marginTop: 8 }}
          />
          <div style={{ marginTop: 6, fontSize: 12, color: "var(--muted)" }}>
            选择文件后直接点击“提交”即可完成上传并入库
          </div>
        </div>

        <div>
          <label className="label">资料类型</label>
          <select
            className="select"
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            style={{ marginTop: 8 }}
          >
            <option value="upload">上传资料</option>
            <option value="resume">简历</option>
            <option value="jd">岗位描述</option>
            <option value="note">笔记</option>
          </select>
        </div>

        <div>
          <label className="label">文本内容</label>
          <textarea
            className="textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="粘贴需要导入的完整文本..."
            style={{ marginTop: 8 }}
          />
          <div style={{ marginTop: 6, fontSize: 12, color: "var(--muted)" }}>
            未选择文件时需要填写文本内容，系统会自动生成 source_id
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="button" type="submit" disabled={loading}>
            {loading ? "提交中..." : "提交"}
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

        {uploadStatus && (
          <div className="banner">{uploadStatus}</div>
        )}

        {resp && (
          <div className="panel">
            <div className="label">返回结果</div>
            {resp.source_id && (
              <div style={{ marginTop: 8, fontSize: 13, color: "var(--muted)" }}>
                已入库：{resp.source_id}（{resp.added ?? 0} 段）
              </div>
            )}
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
