const BASE = import.meta.env.VITE_API_URL ?? "";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type SSEEvent =
  | { type: "token";       content: string }
  | { type: "tool_call";  name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string; content: string }
  | { type: "done" }
  | { type: "error";      content: string };

/**
 * Stream chat responses from the agent via SSE.
 * Calls onEvent for each parsed SSE event.
 * Returns when the stream ends (type: "done") or throws on network error.
 */
export async function streamChat(
  message: string,
  history: ChatMessage[],
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `${BASE}/api/chat/stream`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
    signal,
  });

  if (!resp.ok) {
    throw new Error(`Chat API error: ${resp.status}`);
  }

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data: ")) continue;
      const json = trimmed.slice(6);
      try {
        const event: SSEEvent = JSON.parse(json);
        onEvent(event);
        if (event.type === "done" || event.type === "error") return;
      } catch {
        // Incomplete JSON chunk — ignore
      }
    }
  }
}
