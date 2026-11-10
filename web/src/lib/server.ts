const SERVER = process.env.NEXT_PUBLIC_RUN_SERVER ?? "";

async function headers() {
  const response = await fetch("/api/run-token");
  if (!response.ok) throw new Error("The run server is not set up yet.");
  const { token } = await response.json();
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

async function failure(response: Response) {
  const body = await response.json().catch(() => null);
  return new Error(typeof body?.detail === "string" ? body.detail : "Something went wrong. Try again.");
}

export async function getIdeas(job: object) {
  const response = await fetch(`${SERVER}/ideas`, { method: "POST", headers: await headers(), body: JSON.stringify(job) });
  if (!response.ok) throw await failure(response);
  return (await response.json()).ideas;
}

/** A run takes minutes, so progress arrives as one JSON line at a time. */
export async function startRun(job: object, onEvent: (event: Record<string, unknown>) => void) {
  const response = await fetch(`${SERVER}/run`, { method: "POST", headers: await headers(), body: JSON.stringify(job) });
  if (!response.ok || !response.body) throw await failure(response);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let held = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    held += decoder.decode(value, { stream: true });
    const lines = held.split("\n");
    held = lines.pop() ?? "";
    lines.filter(Boolean).forEach((line) => onEvent(JSON.parse(line)));
  }
}
