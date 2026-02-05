import { proxyToBackend } from "../../../lib/backend";

export async function POST(request: Request) {
  const bodyText = await request.text();
  return proxyToBackend("/retrieve", {
    method: "POST",
    headers: {
      "content-type": request.headers.get("content-type") ?? "application/json",
    },
    body: bodyText,
  });
}
