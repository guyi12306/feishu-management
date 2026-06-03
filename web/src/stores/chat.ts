import { defineStore } from "pinia";
import { ref } from "vue";

import {
  chatApi,
  type Conversation,
  type ConversationDetail,
  type Message,
  type SseEvent,
  type ToolCall,
  type ToolResult,
} from "@/api/chat";
import { settingsApi } from "@/api/settings";

let _msgClientId = -1;
function nextClientId() {
  // 负数代表前端临时 ID,后端确认后会被替换
  return _msgClientId--;
}

export const useChatStore = defineStore("chat", () => {
  const conversations = ref<Conversation[]>([]);
  const current = ref<ConversationDetail | null>(null);
  const sending = ref(false);
  const loadingList = ref(false);
  const llmConfigured = ref<boolean | null>(null);

  async function refreshLlmStatus() {
    try {
      const s = await settingsApi.getLlm();
      llmConfigured.value = s.has_api_key;
    } catch {
      llmConfigured.value = false;
    }
  }

  async function loadList() {
    loadingList.value = true;
    try {
      conversations.value = await chatApi.list();
    } finally {
      loadingList.value = false;
    }
  }

  async function open(id: number) {
    current.value = await chatApi.get(id);
  }

  function reset() {
    current.value = null;
  }

  function ensureCurrent(conv_id?: number): ConversationDetail {
    if (!current.value || (conv_id !== undefined && current.value.id !== conv_id)) {
      current.value = {
        id: conv_id ?? 0,
        title: "新对话",
        updated_at: new Date().toISOString(),
        messages: [],
      };
    }
    return current.value!;
  }

  function appendMessage(m: Message): Message {
    ensureCurrent().messages.push(m);
    return m;
  }

  async function send(content: string): Promise<void> {
    if (sending.value) return;
    sending.value = true;

    if (llmConfigured.value === null) await refreshLlmStatus();

    if (llmConfigured.value) {
      await sendStream(content);
    } else {
      await sendSync(content);
    }
  }

  async function sendSync(content: string) {
    try {
      const result = await chatApi.send(content, current.value?.id);
      if (current.value === null || current.value.id !== result.conversation_id) {
        current.value = await chatApi.get(result.conversation_id);
      } else {
        current.value.messages.push(...result.messages);
      }
      await loadList();
    } finally {
      sending.value = false;
    }
  }

  async function sendStream(content: string) {
    // 1. 立刻把用户消息推到 UI
    const userMsg: Message = {
      id: nextClientId(),
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    appendMessage(userMsg);

    // 2. 占位 assistant
    let streamingAsst: Message | null = null;
    function ensureStreamingAsst(): Message {
      if (streamingAsst) return streamingAsst;
      streamingAsst = {
        id: nextClientId(),
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
        streaming: true,
      };
      appendMessage(streamingAsst);
      return streamingAsst;
    }

    const pendingTools = new Map<string, ToolCall>();

    try {
      for await (const ev of chatApi.stream(content, current.value?.id)) {
        await handleEvent(ev);
      }
    } catch (e: any) {
      const a = ensureStreamingAsst();
      a.content = (a.content ?? "") + `\n\n[错误]${e?.message ?? e}`;
      a.streaming = false;
    } finally {
      const finalAsst = streamingAsst as Message | null;
      if (finalAsst) finalAsst.streaming = false;
      sending.value = false;
      await loadList();
    }

    async function handleEvent(ev: SseEvent) {
      if (ev.event === "started") {
        const conv_id = ev.data.conversation_id as number;
        if (current.value && current.value.id !== conv_id) {
          current.value.id = conv_id;
        }
        // 用真实的 user_message_id 替换占位 id
        if (ev.data.user_message_id) {
          userMsg.id = ev.data.user_message_id;
        }
      } else if (ev.event === "token") {
        const a = ensureStreamingAsst();
        a.content = (a.content ?? "") + (ev.data.text ?? "");
      } else if (ev.event === "tool_call") {
        const a = ensureStreamingAsst();
        const tc: ToolCall = {
          id: ev.data.tool_call_id,
          type: "function",
          function: { name: ev.data.name, arguments: ev.data.arguments_raw ?? "" },
        };
        a.tool_calls = [...(a.tool_calls ?? []), tc];
        pendingTools.set(tc.id, tc);
      } else if (ev.event === "tool_result") {
        const result: ToolResult = {
          tool_call_id: ev.data.tool_call_id,
          name: ev.data.name,
          ok: !!ev.data.ok,
          result: ev.data.result,
        };
        appendMessage({
          id: nextClientId(),
          role: "tool",
          content: null,
          tool_result: result,
          created_at: new Date().toISOString(),
        });
        pendingTools.delete(result.tool_call_id);
      } else if (ev.event === "message_complete") {
        const a = ensureStreamingAsst();
        a.id = ev.data.message_id ?? a.id;
        a.content = ev.data.content ?? a.content;
        a.draft_id = ev.data.draft_id ?? a.draft_id ?? null;
        a.streaming = false;
        streamingAsst = null; // 下一轮开新的助手消息
      } else if (ev.event === "draft_attached") {
        // 给已 finalize 的 assistant 消息回填 draft_id
        const msgs = current.value?.messages ?? [];
        const target = [...msgs].reverse().find(
          (m) => m.role === "assistant" && m.id === ev.data.message_id
        );
        if (target) target.draft_id = ev.data.draft_id;
      } else if (ev.event === "error") {
        const a = ensureStreamingAsst();
        a.content = (a.content ?? "") + `\n\n[错误]${ev.data.message}`;
        a.streaming = false;
      } else if (ev.event === "done") {
        // 结束;什么都不用做
      }
    }
  }

  async function removeConversation(id: number) {
    await chatApi.delete(id);
    conversations.value = conversations.value.filter((c) => c.id !== id);
    if (current.value?.id === id) current.value = null;
  }

  async function rename(id: number, title: string) {
    const c = await chatApi.rename(id, title);
    const item = conversations.value.find((x) => x.id === id);
    if (item) item.title = c.title;
    if (current.value?.id === id) current.value.title = c.title;
  }

  return {
    conversations,
    current,
    sending,
    loadingList,
    llmConfigured,
    refreshLlmStatus,
    loadList,
    open,
    reset,
    send,
    removeConversation,
    rename,
  };
});
