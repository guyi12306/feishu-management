import client from "./client";

export type MessageRole = "user" | "assistant" | "tool";

export interface ToolCall {
  id: string;
  type: "function";
  function: { name: string; arguments: string };
}

export interface ToolResult {
  tool_call_id: string;
  name: string;
  ok: boolean;
  result: unknown;
}

export interface Message {
  id: number;
  role: MessageRole;
  content: string | null;
  tool_calls?: ToolCall[] | null;
  tool_result?: ToolResult | null;
  draft_id?: number | null;
  created_at: string;
  /** 仅前端使用,标记正在流式接收中 */
  streaming?: boolean;
}

export interface Conversation {
  id: number;
  title: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export const chatApi = {
  async list(): Promise<Conversation[]> {
    const { data } = await client.get("/conversations");
    return data;
  },
  async create(title?: string): Promise<Conversation> {
    const { data } = await client.post("/conversations", { title });
    return data;
  },
  async get(id: number): Promise<ConversationDetail> {
    const { data } = await client.get(`/conversations/${id}`);
    return data;
  },
  async delete(id: number): Promise<void> {
    await client.delete(`/conversations/${id}`);
  },
  async send(
    content: string,
    conversation_id?: number
  ): Promise<{ conversation_id: number; messages: Message[]; mode?: string }> {
    const { data } = await client.post("/chat", { content, conversation_id });
    return data;
  },

  async rename(id: number, title: string): Promise<Conversation> {
    const { data } = await client.put(`/conversations/${id}`, { title });
    return data;
  },

  async *stream(
    content: string,
    conversation_id: number | undefined,
    signal?: AbortSignal
  ): AsyncGenerator<SseEvent, void, unknown> {
    const resp = await fetch("/api/chat/stream", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ content, conversation_id }),
      signal,
    });
    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${err}`);
    }
    if (!resp.body) throw new Error("响应没有 body");

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      // SSE 事件以 \n\n 分隔
      let idx: number;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const ev = parseSseEvent(raw);
        if (ev) yield ev;
      }
    }
  },
};

export interface SseEvent {
  event: string;
  data: any;
}

function parseSseEvent(raw: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  const dataStr = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(dataStr) };
  } catch {
    return { event, data: dataStr };
  }
}
