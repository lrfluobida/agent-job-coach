"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  stage?: string;
  stageText?: string;
  citations?: Citation[];
  used_context?: UsedContext[];
  isStreaming?: boolean;
};

type Citation = {
  id: string;
  quote?: string;
};

type UsedContext = {
  id?: string;
  text?: string;
  metadata?: Record<string, unknown>;
  score?: number;
};

type UploadSourceType = "resume" | "jd" | "note";

type ActiveSource = {
  source_id: string;
  source_type: UploadSourceType;
  filename: string;
} | null;

function normalizeCitations(input: unknown): Citation[] {
  if (!Array.isArray(input)) return [];
  const out: Citation[] = [];
  for (const item of input) {
    if (typeof item === "string") {
      out.push({ id: item });
    } else if (item && typeof item === "object") {
      const maybe = item as Citation;
      if (typeof maybe.id === "string" && maybe.id.length > 0) {
        out.push(maybe);
      }
    }
  }
  return out;
}

function hasUnclosedFence(text: string) {
  const matches = text.match(/```/g);
  return (matches?.length ?? 0) % 2 === 1;
}

function makeTitle(text: string) {
  const trimmed = text.trim();
  const maxLen = 20;
  if (trimmed.length <= maxLen) return trimmed || "新对话";
  return `${trimmed.slice(0, maxLen)}...`;
}

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [title, setTitle] = useState("新对话");
  const [openEvidenceIndex, setOpenEvidenceIndex] = useState<number | null>(null);
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});
  const [expandedMeta, setExpandedMeta] = useState<Record<string, boolean>>({});
  const [uploadType, setUploadType] = useState<UploadSourceType>("resume");
  const [uploading, setUploading] = useState(false);
  const [activeSource, setActiveSource] = useState<ActiveSource>(null);
  const [mode, setMode] = useState<"chat" | "resume_interview">("chat");
  const [hydrated, setHydrated] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const evidenceRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const assistantIndexRef = useRef<number | null>(null);
  const streamControllerRef = useRef<AbortController | null>(null);

  const resetChat = useCallback(() => {
    streamControllerRef.current?.abort();
    streamControllerRef.current = null;
    assistantIndexRef.current = null;
    setMessages([]);
    setInput("");
    setLoading(false);
    setErr("");
    setTitle("新对话");
    setOpenEvidenceIndex(null);
    setExpandedEvidence({});
    setExpandedMeta({});
    setMode("chat");
    setActiveSource(null);
  }, []);

  const canSend = useMemo(() => input.trim().length > 0 && !loading, [input, loading]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("jobcoach_chat_state");
      if (!saved) return;
      const data = JSON.parse(saved) as {
        messages?: ChatMessage[];
        input?: string;
        title?: string;
        uploadType?: UploadSourceType;
        activeSource?: ActiveSource;
        mode?: "chat" | "resume_interview";
      };
      if (Array.isArray(data.messages)) {
        const restored = data.messages.map((msg) => ({
          ...msg,
          isStreaming: false,
          stageText: msg.stage === "aborted" ? "已中断" : "",
        }));
        setMessages(restored);
      }
      if (typeof data.input === "string") setInput(data.input);
      if (typeof data.title === "string") setTitle(data.title);
      if (data.uploadType === "resume" || data.uploadType === "jd" || data.uploadType === "note") {
        setUploadType(data.uploadType);
      }
      if (
        data.activeSource &&
        typeof data.activeSource.source_id === "string" &&
        (data.activeSource.source_type === "resume" ||
          data.activeSource.source_type === "jd" ||
          data.activeSource.source_type === "note")
      ) {
        setActiveSource(data.activeSource);
      }
      if (data.mode === "chat" || data.mode === "resume_interview") {
        setMode(data.mode);
      }
    } catch {
      // ignore corrupted cache
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key.toLowerCase() === "k") {
        event.preventDefault();
        textareaRef.current?.focus();
      }
      if (event.key === "Escape") {
        textareaRef.current?.blur();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, loading]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      const snapshot = {
        messages,
        input,
        title,
        uploadType,
        activeSource,
        mode,
      };
      localStorage.setItem("jobcoach_chat_state", JSON.stringify(snapshot));
    } catch {
      // ignore storage errors
    }
  }, [messages, input, title, uploadType, activeSource, mode, hydrated]);

  useEffect(() => {
    return () => {
      streamControllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const onNewChat = () => {
      resetChat();
    };
    window.addEventListener("jobcoach:new-chat", onNewChat as EventListener);
    return () => window.removeEventListener("jobcoach:new-chat", onNewChat as EventListener);
  }, [resetChat]);

  const updateAssistant = (updater: (msg: ChatMessage) => ChatMessage) => {
    const index = assistantIndexRef.current;
    if (index === null) return;
    setMessages((prev) => {
      if (index < 0 || index >= prev.length) return prev;
      const next = [...prev];
      next[index] = updater(next[index]);
      return next;
    });
  };

  const abortCurrentStream = () => {
    if (streamControllerRef.current) {
      streamControllerRef.current.abort();
      streamControllerRef.current = null;
      updateAssistant((prev) => ({
        ...prev,
        stage: "aborted",
        stageText: "已中断",
        isStreaming: false,
      }));
      setLoading(false);
    }
  };

  const uploadFile = async (file: File, sourceType: UploadSourceType) => {
    const form = new FormData();
    form.append("file", file);
    form.append("source_type", sourceType);

    const res = await fetch("/api/ingest/file", {
      method: "POST",
      body: form,
    });

    const text = await res.text();
    let data: Record<string, unknown> = {};
    try {
      data = JSON.parse(text) as Record<string, unknown>;
    } catch {
      data = {};
    }

    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`;
      throw new Error(detail);
    }

    const sourceId = typeof data.source_id === "string" ? data.source_id : "";
    if (!sourceId) {
      throw new Error("upload succeeded but source_id is missing");
    }

    setActiveSource({
      source_id: sourceId,
      source_type: sourceType,
      filename: file.name,
    });
    setErr("");
  };

  const onPickFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;
    setUploading(true);
    try {
      await uploadFile(file, uploadType);
    } catch (e: unknown) {
      setErr(getErrorMessage(e));
    } finally {
      setUploading(false);
    }
  };

  const sendMessage = async () => {
    if (!canSend) return;

    abortCurrentStream();

    const userMessage: ChatMessage = { role: "user", content: input.trim() };
    const historyPayload = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));
    const resumeInterviewIntent = /简历|面试|提问|追问|mock|interview/i.test(userMessage.content);
    const nextMode: "chat" | "resume_interview" =
      activeSource?.source_type === "resume" && (mode === "resume_interview" || resumeInterviewIntent)
        ? "resume_interview"
        : "chat";
    setMode(nextMode);
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setErr("");

    if (messages.length === 0) {
      setTitle(makeTitle(userMessage.content));
    }

    setMessages((prev) => {
      const next = [
        ...prev,
        {
          role: "assistant" as const,
          content: "",
          stage: "retrieve",
          stageText: "正在检索你的资料...",
          citations: [],
          used_context: [],
          isStreaming: true,
        },
      ];
      assistantIndexRef.current = next.length - 1;
      return next;
    });

    const controller = new AbortController();
    streamControllerRef.current = controller;

    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          message: userMessage.content,
          history: historyPayload,
          mode: nextMode,
          active_source_id: activeSource?.source_id ?? null,
          active_source_type: activeSource?.source_type ?? null,
        }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const lines = part.split("\n");
          let event = "message";
          const dataLines: string[] = [];
          for (const line of lines) {
            if (line.startsWith("event:")) {
              event = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataLines.push(line.slice(5).trimStart());
            }
          }
          const dataStr = dataLines.join("\n");
          if (!dataStr) continue;

          let data: unknown;
          try {
            data = JSON.parse(dataStr);
          } catch {
            continue;
          }
          if (!isRecord(data)) continue;

          if (event === "status") {
            const stageMap: Record<string, string> = {
              retrieve: "正在检索你的资料...",
              generate: "正在组织回答...",
              finalize: "正在整理引用...",
            };
            const stage = typeof data.stage === "string" ? data.stage : undefined;
            const message = typeof data.message === "string" ? data.message : undefined;
            const mapped = (stage ? stageMap[stage] : undefined) ?? message;
            updateAssistant((prev) => ({
              ...prev,
              stage: stage ?? prev.stage,
              stageText: mapped ?? prev.stageText,
              isStreaming: true,
            }));
          } else if (event === "token") {
            const delta = typeof data.delta === "string" ? data.delta : "";
            updateAssistant((prev) => ({
              ...prev,
              content: `${prev.content}${delta}`,
              isStreaming: true,
            }));
          } else if (event === "context") {
            updateAssistant((prev) => ({
              ...prev,
              citations: normalizeCitations(data.citations),
              used_context: Array.isArray(data.used_context) ? data.used_context : [],
            }));
          } else if (event === "done") {
            updateAssistant((prev) => ({
              ...prev,
              stage: "done",
              isStreaming: false,
            }));
            setTimeout(() => {
              updateAssistant((prev) => ({
                ...prev,
                stageText: "",
              }));
            }, 800);
            setLoading(false);
          } else if (event === "error") {
            const errorText =
              typeof data.error === "string" && data.error.trim()
                ? data.error
                : "抱歉，流式生成失败，请稍后重试。";
            updateAssistant((prev) => ({
              ...prev,
              content: errorText,
              stage: "error",
              stageText: "出错",
              isStreaming: false,
            }));
            setErr(errorText);
            setLoading(false);
          }
        }
      }
    } catch (e: unknown) {
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        const message = getErrorMessage(e);
        setErr(message);
        updateAssistant((prev) => ({
          ...prev,
          content: `抱歉，流式生成失败：${message}`,
          stage: "error",
          stageText: "出错",
          isStreaming: false,
        }));
      }
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void sendMessage();
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  const handleChipClick = (messageIndex: number, contextId: string) => {
    setOpenEvidenceIndex(messageIndex);
    const key = `${messageIndex}:${contextId}`;
    setTimeout(() => {
      evidenceRefs.current[key]?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
  };

  return (
    <div className="container">
      <div className="page-header">
        <h1 className="page-title">{title}</h1>
        <p className="page-subtitle">Shift + Enter 换行，Enter 发送。Ctrl + K 聚焦输入框。</p>
      </div>

      {err && <div className="banner" style={{ marginBottom: 16 }}>{err}</div>}

      <div className="panel" style={{ padding: 20 }}>
        <div className="chat-window" ref={listRef}>
          {messages.length === 0 && (
            <div style={{ color: "var(--muted)" }}>
              还没有消息。可以先让助手帮你优化简历或准备面试。
            </div>
          )}
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`chat-bubble ${msg.role}`}
              style={{
                maxWidth: "75%",
                wordBreak: "break-word",
              }}
            >
              <div style={{ fontSize: 12, textTransform: "uppercase", opacity: 0.6 }}>
                {msg.role === "user" ? "你" : "助手"}
              </div>
              {msg.role === "assistant" &&
                (msg.isStreaming || msg.stage === "aborted" || msg.stage === "error") &&
                msg.stageText && (
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
                  {msg.stageText}
                </div>
              )}
              {msg.role === "assistant" ? (
                msg.isStreaming && hasUnclosedFence(msg.content) ? (
                  <pre style={{ whiteSpace: "pre-wrap", marginTop: 4, fontFamily: "inherit" }}>
                    {msg.content}
                  </pre>
                ) : (
                  <div style={{ marginTop: 4 }}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        ul: ({ children }) => (
                          <ul style={{ paddingLeft: 20, listStyle: "disc" }}>{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol style={{ paddingLeft: 20, listStyle: "decimal" }}>{children}</ol>
                        ),
                        code: ({ children, className }) => (
                          <code
                            style={{
                              background: "rgba(0,0,0,0.08)",
                              padding: "2px 4px",
                              borderRadius: 4,
                              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace",
                            }}
                            className={className}
                          >
                            {children}
                          </code>
                        ),
                        pre: ({ children }) => (
                          <pre
                            style={{
                              whiteSpace: "pre-wrap",
                              background: "rgba(0,0,0,0.08)",
                              padding: 10,
                              borderRadius: 8,
                              overflowX: "auto",
                            }}
                          >
                            {children}
                          </pre>
                        ),
                        a: ({ children, href }) => (
                          <a href={href} target="_blank" rel="noreferrer">
                            {children}
                          </a>
                        ),
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )
              ) : (
                <div style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>{msg.content}</div>
              )}
              {msg.role === "assistant" && (
                <>
                  {(msg.citations ?? []).length > 0 ? (
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: 8,
                        marginTop: 10,
                      }}
                    >
                      {(msg.citations ?? []).map((c, idx) => (
                        <button
                          key={`${c.id}-${idx}`}
                          type="button"
                          onClick={() => handleChipClick(index, c.id)}
                          style={{
                            padding: "4px 8px",
                            borderRadius: 999,
                            border: "1px solid var(--border)",
                            fontSize: 12,
                            background: "var(--panel)",
                            cursor: "pointer",
                          }}
                        >
                          {c.id}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted)" }}>
                      无引用证据（模型未使用检索片段）
                    </div>
                  )}
                  {(msg.citations ?? []).length > 0 && (msg.used_context ?? []).length > 0 && (
                    <details style={{ marginTop: 10 }} open={openEvidenceIndex === index}>
                      <summary style={{ cursor: "pointer", color: "var(--muted)" }}>
                        查看证据（{msg.citations?.length ?? 0}）
                      </summary>
                      <div style={{ marginTop: 8, display: "grid", gap: 12 }}>
                        {(msg.used_context ?? [])
                          .filter((item) =>
                            (msg.citations ?? []).some((c) => c.id === item.id),
                          )
                          .map((item, idx) => {
                        const contextId = item.id ?? `ctx-${idx}`;
                        const key = `${index}:${contextId}`;
                        const text = item.text ?? "";
                        const quote =
                          (msg.citations ?? []).find((c) => c.id === item.id)?.quote ?? "";
                        const isExpanded = expandedEvidence[key];
                        const metaExpanded = expandedMeta[key];
                        const previewBase = quote || text;
                        const shortText =
                          previewBase.length > 160 ? `${previewBase.slice(0, 160)}...` : previewBase;
                        const displayText = isExpanded ? text || quote : shortText;
                        const score =
                          typeof item.score === "number" ? item.score.toFixed(3) : "n/a";
                        const filename = item.metadata?.filename as string | undefined;

                        return (
                          <div
                            key={key}
                            ref={(el) => {
                              evidenceRefs.current[key] = el;
                            }}
                            style={{
                              border: "1px solid var(--border)",
                              borderRadius: 12,
                              padding: 12,
                              background: "rgba(0,0,0,0.02)",
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                gap: 12,
                                fontSize: 13,
                              }}
                            >
                              <span style={{ fontWeight: 600 }}>
                                {filename ? `${filename} · ${contextId}` : contextId}
                              </span>
                              <span style={{ color: "var(--muted)" }}>相似度 {score}</span>
                            </div>
                            <div
                              style={{
                                marginTop: 8,
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-word",
                              }}
                            >
                              {displayText}
                            </div>
                            {text.length > 160 && (
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedEvidence((prev) => ({
                                    ...prev,
                                    [key]: !prev[key],
                                  }))
                                }
                                style={{
                                  marginTop: 8,
                                  border: "none",
                                  background: "transparent",
                                  color: "var(--accent)",
                                  cursor: "pointer",
                                }}
                              >
                                {isExpanded ? "收起" : "展开"}
                              </button>
                            )}
                            {item.metadata && (
                              <div style={{ marginTop: 8 }}>
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedMeta((prev) => ({
                                      ...prev,
                                      [key]: !prev[key],
                                    }))
                                  }
                                  style={{
                                    border: "none",
                                    background: "transparent",
                                    color: "var(--muted)",
                                    cursor: "pointer",
                                    fontSize: 12,
                                  }}
                                >
                                  {metaExpanded ? "收起更多信息" : "更多信息"}
                                </button>
                                {metaExpanded && (
                                  <pre
                                    style={{
                                      marginTop: 6,
                                      whiteSpace: "pre-wrap",
                                      wordBreak: "break-word",
                                      fontSize: 12,
                                      background: "rgba(0,0,0,0.04)",
                                      padding: 8,
                                      borderRadius: 8,
                                    }}
                                  >
                                    {JSON.stringify(item.metadata, null, 2)}
                                  </pre>
                                )}
                              </div>
                            )}
                          </div>
                        );
                        })}
                      </div>
                    </details>
                  )}
                </>
              )}
            </div>
          ))}
        </div>

        <form onSubmit={onSubmit} className="composer" style={{ marginTop: 16 }}>
          <div
            style={{
              fontSize: 12,
              color: "var(--muted)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "6px 10px",
              background: "var(--panel)",
              alignSelf: "flex-start",
            }}
          >
            {activeSource
              ? `当前资料：${activeSource.source_type} · ${activeSource.filename}`
              : "当前资料：未绑定"}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.md,.txt"
            style={{ display: "none" }}
            onChange={onPickFile}
          />
          <textarea
            ref={textareaRef}
            className="textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="输入你的问题，回车发送..."
            rows={3}
          />
          <div className="composer-actions">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button
                type="button"
                className="button secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || loading}
                style={{ padding: "6px 10px", lineHeight: 1 }}
                title="上传资料"
              >
                {uploading ? "..." : "+"}
              </button>
              <select
                className="select"
                value={uploadType}
                onChange={(e) => setUploadType(e.target.value as UploadSourceType)}
                disabled={uploading || loading}
                style={{ width: 110, padding: "8px 10px", borderRadius: 10 }}
              >
                <option value="resume">resume</option>
                <option value="jd">jd</option>
                <option value="note">note</option>
              </select>
              <span style={{ color: "var(--muted)", fontSize: 12 }}>
                Esc 取消聚焦 · Ctrl + K 聚焦
              </span>
            </div>
            <button className="button" type="submit" disabled={!canSend}>
              {loading ? "发送中..." : "发送"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
