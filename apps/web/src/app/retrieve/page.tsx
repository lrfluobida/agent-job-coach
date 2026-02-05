"use client";

import { useEffect, useRef, useState } from "react";

type RetrieveResult = {
  score?: number;
  metadata?: Record<string, unknown>;
  text?: string;
  document?: string;
};

type RetrieveResponse = {
  ok?: boolean;
  results?: RetrieveResult[];
  matches?: RetrieveResult[];
  error?: string;
};

export default function RetrievePage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [sourceType, setSourceType] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [resp, setResp] = useState<RetrieveResponse | null>(null);
  const [raw, setRaw] = useState<string>("");
  const [err, setErr] = useState<string>("");
  const [banner, setBanner] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const hydratedRef = useRef(false);
  const stateRef = useRef({
    query: "",
    topK: 5,
    sourceType: "",
    sourceId: "",
    resp: null as RetrieveResponse | null,
    raw: "",
    err: "",
    banner: "",
  });

  useEffect(() => {
    try {
      const saved = localStorage.getItem("jobcoach_retrieve_state");
      if (!saved) return;
      const data = JSON.parse(saved) as {
        query?: string;
        topK?: number;
        sourceType?: string;
        sourceId?: string;
        resp?: RetrieveResponse | null;
        raw?: string;
        err?: string;
        banner?: string;
      };
      if (typeof data.query === "string") setQuery(data.query);
      if (typeof data.topK === "number") setTopK(data.topK);
      if (typeof data.sourceType === "string") setSourceType(data.sourceType);
      if (typeof data.sourceId === "string") setSourceId(data.sourceId);
      if (typeof data.raw === "string") setRaw(data.raw);
      if (typeof data.err === "string") setErr(data.err);
      if (typeof data.banner === "string") setBanner(data.banner);
      if (data.resp) setResp(data.resp);
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
        query,
        topK,
        sourceType,
        sourceId,
        resp,
        raw,
        err,
        banner,
      };
      stateRef.current = snapshot;
      localStorage.setItem("jobcoach_retrieve_state", JSON.stringify(snapshot));
    } catch {
      // ignore storage errors
    }
  }, [query, topK, sourceType, sourceId, resp, raw, err, banner]);

  useEffect(() => {
    return () => {
      try {
        localStorage.setItem("jobcoach_retrieve_state", JSON.stringify(stateRef.current));
      } catch {
        // ignore storage errors
      }
    };
  }, []);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setErr("");
    setBanner("");
    setResp(null);
    setRaw("");

    const filter: Record<string, string> = {};
    if (sourceType) filter.source_type = sourceType;
    if (sourceId) filter.source_id = sourceId;

    try {
      const res = await fetch("/api/retrieve", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          query,
          top_k: topK,
          filter: Object.keys(filter).length ? filter : undefined,
        }),
      });

      const bodyText = await res.text();
      if (res.status === 404) {
        setBanner("检索接口暂未实现，请先在后端添加 /retrieve 后再使用本页面。");
        return;
      }
      if (!res.ok) {
        throw new Error(bodyText || `HTTP ${res.status}`);
      }
      setRaw(bodyText);
      const json = JSON.parse(bodyText) as RetrieveResponse;
      setResp(json);
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  };

  const list = resp?.results ?? resp?.matches ?? [];

  return (
    <div className="container">
      <div className="page-header">
        <h1 className="page-title">检索调试</h1>
        <p className="page-subtitle">按查询语句检索向量库并查看匹配结果。</p>
      </div>

      {banner && <div className="banner" style={{ marginBottom: 16 }}>{banner}</div>}

      <form className="panel panel-grid" onSubmit={onSubmit}>
        <div>
          <label className="label">查询</label>
          <input
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="例如：突出领导力成果"
            style={{ marginTop: 8 }}
            required
          />
        </div>

        <div className="panel-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          <div>
            <label className="label">Top K</label>
            <input
              className="input"
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              style={{ marginTop: 8 }}
            />
          </div>
          <div>
            <label className="label">过滤 source_type</label>
            <select
              className="select"
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              style={{ marginTop: 8 }}
            >
              <option value="">不限</option>
              <option value="jd">jd</option>
              <option value="resume">resume</option>
              <option value="note">note</option>
            </select>
          </div>
        </div>

        <div>
          <label className="label">过滤 source_id</label>
          <input
            className="input"
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            placeholder="可选"
            style={{ marginTop: 8 }}
          />
        </div>

        <div>
          <button className="button secondary" type="submit" disabled={loading}>
            {loading ? "检索中..." : "开始检索"}
          </button>
        </div>
      </form>

      <section className="panel-grid" style={{ marginTop: 20 }}>
        {loading && (
          <div className="panel panel-grid">
            <div className="skeleton" style={{ width: "50%" }} />
            <div className="skeleton" style={{ width: "80%" }} />
            <div className="skeleton" style={{ width: "65%" }} />
          </div>
        )}

        {list.length > 0 && (
          <div className="panel panel-grid">
            <div className="label">匹配结果</div>
            {list.map((item, index) => (
              <div key={index} className="panel" style={{ boxShadow: "none" }}>
                <div className="label">Score</div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>
                  {item.score ?? "n/a"}
                </div>
                <div className="label" style={{ marginTop: 10 }}>
                  Metadata
                </div>
                <pre className="codeblock" style={{ marginTop: 6 }}>
                  {JSON.stringify(item.metadata ?? {}, null, 2)}
                </pre>
                <div className="label" style={{ marginTop: 10 }}>
                  文本
                </div>
                <p style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>
                  {item.text ?? item.document ?? ""}
                </p>
              </div>
            ))}
          </div>
        )}

        {raw && list.length === 0 && !loading && (
          <div className="panel">
            <div className="label">原始返回</div>
            <pre className="codeblock" style={{ marginTop: 10 }}>
              {raw}
            </pre>
          </div>
        )}

        {!loading && !banner && !err && !raw && list.length === 0 && (
          <div className="panel">
            <div className="label">暂无结果</div>
            <p style={{ marginTop: 8, color: "var(--muted)" }}>
              提交查询后这里会显示匹配内容。
            </p>
          </div>
        )}

        {err && <div className="banner">{err}</div>}
      </section>
    </div>
  );
}
