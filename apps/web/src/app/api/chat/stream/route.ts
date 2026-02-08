import { getBackendBase } from "../../../../lib/backend";

export async function POST(request: Request) {
  const bodyText = await request.text();
  let payload: {
    message?: string;
    top_k?: number;
    history?: Array<{ role: string; content: string }>;
    mode?: string;
    active_source_id?: string;
    active_source_type?: string;
    conversation_id?: string;
    request_id?: string;
  } = {};
  try {
    payload = JSON.parse(bodyText);
  } catch {
    payload = {};
  }

  const forwardBody = JSON.stringify({
    question: payload.message ?? "",
    top_k: payload.top_k ?? 5,
    history: payload.history ?? [],
    mode: payload.mode ?? "chat",
    active_source_id: payload.active_source_id ?? null,
    active_source_type: payload.active_source_type ?? null,
    conversation_id: payload.conversation_id ?? null,
    request_id: payload.request_id ?? null,
  });

  const backendBase = getBackendBase();
  const res = await fetch(`${backendBase}/chat/stream`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: forwardBody,
  });

  const headers = new Headers(res.headers);
  headers.set("content-type", "text/event-stream; charset=utf-8");
  headers.set("cache-control", "no-cache");

  return new Response(res.body, {
    status: res.status,
    headers,
  });
}
