import { proxyToBackend } from "../../../lib/backend";

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

  return proxyToBackend("/skills/interview_qa", {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: forwardBody,
  });
}
