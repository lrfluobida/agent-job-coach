import { getBackendBase } from "../../../../lib/backend";

export async function POST(request: Request) {
  const bodyText = await request.text();
  let payload: { message?: string; top_k?: number } = {};
  try {
    payload = JSON.parse(bodyText);
  } catch {
    payload = {};
  }

  const forwardBody = JSON.stringify({
    question: payload.message ?? "",
    top_k: payload.top_k ?? 5,
    filter: { source_type: "resume" },
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
