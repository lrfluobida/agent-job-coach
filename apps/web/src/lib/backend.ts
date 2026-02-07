const DEFAULT_BACKEND_BASE = "http://127.0.0.1:8000";

export function getBackendBase(): string {
  return process.env.BACKEND_API_BASE ?? DEFAULT_BACKEND_BASE;
}

function jsonError(message: string, status = 502): Response {
  return new Response(JSON.stringify({ ok: false, error: message }), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export async function proxyToBackend(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const base = getBackendBase();
  const url = `${base}${path}`;

  try {
    const response = await fetch(url, {
      ...init,
      cache: "no-store",
    });

    const contentType = response.headers.get("content-type") ?? "text/plain";
    const bodyText = await response.text();

    return new Response(bodyText, {
      status: response.status,
      headers: { "content-type": contentType },
    });
  } catch (err: unknown) {
    return jsonError(getErrorMessage(err), 502);
  }
}
