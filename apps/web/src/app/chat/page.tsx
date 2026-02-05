"use client";

import { useEffect, useMemo, useRef, useState } from "react";

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

type InterviewQAResponse = {
  ok?: boolean;
  answer?: string;
  citations?: Citation[];
  used_context?: UsedContext[];
  error?: string;
};

function makeTitle(text: string) {
  const trimmed = text.trim();
  const maxLen = 20;
  if (trimmed.length <= maxLen) return trimmed || "新对话";
  return `${trimmed.slice(0, maxLen)}...`;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [banner, setBanner] = useState("");
  const [err, setErr] = useState("");
  const [title, setTitle] = useState("新对话");
  const [openEvidenceIndex, setOpenEvidenceIndex] = useState<number | null>(null);
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});
  const [expandedMeta, setExpandedMeta] = useState<Record<string, boolean>>({});
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const evidenceRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const assistantIndexRef = useRef<number | null>(null);
  const streamControllerRef = useRef<AbortController | null>(null);

  const canSend = useMemo(() => input.trim().length > 0 && !loading, [input, loading]);

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
    return () => {
      streamControllerRef.current?.abort();
    };
  }, []);

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

  const runNonStream = async (question: string) => {
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: question }),
      });

      const bodyText = await res.text();
      if (res.status === 404) {
        setBanner("聊天接口暂未实现，请先在后端添加 /chat 后再使用本页面。");
        return;
      }
      if (!res.ok) {
        throw new Error(bodyText || `HTTP ${res.status}`);
      }

      let payload: InterviewQAResponse | null = null;
      try {
        const json = JSON.parse(bodyText) as InterviewQAResponse;
        if (typeof json.answer === "string") {
          payload = json;
        } else {
          console.warn("聊天接口返回缺少 answer 字段", json);
        }
      } catch (err) {
        console.warn("聊天接口返回非 JSON：", bodyText, err);
      }

      if (!payload) {
        updateAssistant((prev) => ({
          ...prev,
          content: "抱歉，助手返回的数据解析失败，请稍后重试。",
          stage: "error",
          stageText: "出错",
          isStreaming: false,
        }));
        return;
      }

      updateAssistant((prev) => ({
        ...prev,
        content: payload.answer ?? "",
        citations: Array.isArray(payload.citations) ? payload.citations : [],
        used_context: Array.isArray(payload.used_context) ? payload.used_context : [],
        stage: "done",
        stageText: "",
        isStreaming: false,
      }));
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    }
  };

  const sendMessage = async () => {
    if (!canSend) return;

    abortCurrentStream();

    const userMessage: ChatMessage = { role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setBanner("");
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
        body: JSON.stringify({ message: userMessage.content }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        await runNonStream(userMessage.content);
        return;
      }

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

          let data: any;
          try {
            data = JSON.parse(dataStr);
          } catch {
            continue;
          }

          if (event === "status") {
            const stageMap: Record<string, string> = {
              retrieve: "正在检索你的资料...",
              generate: "正在组织回答...",
              finalize: "正在整理引用...",
            };
            const mapped = stageMap[data.stage] ?? data.message;
            updateAssistant((prev) => ({
              ...prev,
              stage: data.stage ?? prev.stage,
              stageText: mapped ?? prev.stageText,
              isStreaming: true,
            }));
          } else if (event === "token") {
            updateAssistant((prev) => ({
              ...prev,
              content: `${prev.content}${data.delta ?? ""}`,
              isStreaming: true,
            }));
          } else if (event === "context") {
            updateAssistant((prev) => ({
              ...prev,
              citations: Array.isArray(data.citations) ? data.citations : [],
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
            updateAssistant((prev) => ({
              ...prev,
              content: "抱歉，流式生成失败，请稍后重试。",
              stage: "error",
              stageText: "出错",
              isStreaming: false,
            }));
            setLoading(false);
          }
        }
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        await runNonStream(userMessage.content);
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

      {banner && <div className="banner" style={{ marginBottom: 16 }}>{banner}</div>}
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
                overflow: "hidden",
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
              <div style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>{msg.content}</div>
              {msg.role === "assistant" && (
                <>
                  {(msg.citations ?? []).length > 0 && (
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
                  )}
                  <details style={{ marginTop: 10 }} open={openEvidenceIndex === index}>
                    <summary style={{ cursor: "pointer", color: "var(--muted)" }}>
                      查看证据（{msg.used_context?.length ?? 0}）
                    </summary>
                    <div style={{ marginTop: 8, display: "grid", gap: 12 }}>
                      {(msg.used_context ?? []).map((item, idx) => {
                        const contextId = item.id ?? `ctx-${idx}`;
                        const key = `${index}:${contextId}`;
                        const text = item.text ?? "";
                        const isExpanded = expandedEvidence[key];
                        const metaExpanded = expandedMeta[key];
                        const shortText =
                          text.length > 160 ? `${text.slice(0, 160)}...` : text;
                        const score =
                          typeof item.score === "number" ? item.score.toFixed(3) : "n/a";

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
                              <span style={{ fontWeight: 600 }}>{contextId}</span>
                              <span style={{ color: "var(--muted)" }}>相似度 {score}</span>
                            </div>
                            <div
                              style={{
                                marginTop: 8,
                                whiteSpace: "pre-wrap",
                                wordBreak: "break-word",
                              }}
                            >
                              {isExpanded ? text : shortText}
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
                </>
              )}
            </div>
          ))}
        </div>

        <form onSubmit={onSubmit} className="composer" style={{ marginTop: 16 }}>
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
            <span style={{ color: "var(--muted)", fontSize: 12 }}>
              Esc 取消聚焦 · Ctrl + K 聚焦
            </span>
            <button className="button" type="submit" disabled={!canSend}>
              {loading ? "发送中..." : "发送"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
