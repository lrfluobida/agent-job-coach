import { getBackendBase } from "../../../../lib/backend";

export async function POST(request: Request) {
  const backendBase = getBackendBase();
  const res = await fetch(`${backendBase}/ingest/file`, {
    method: "POST",
    body: request.body,
    headers: {
      "content-type": request.headers.get("content-type") ?? "multipart/form-data",
    },
    duplex: "half",
  } as RequestInit);

  return new Response(res.body, {
    status: res.status,
    headers: res.headers,
  });
}
