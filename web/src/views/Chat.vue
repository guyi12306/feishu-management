<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Sparkles } from "lucide-vue-next";

import ChatInput from "@/components/chat/ChatInput.vue";
import ConversationList from "@/components/chat/ConversationList.vue";
import MessageBubble from "@/components/chat/MessageBubble.vue";
import { useChatStore } from "@/stores/chat";

const chat = useChatStore();
const route = useRoute();
const router = useRouter();

const scrollEl = ref<HTMLDivElement | null>(null);

const messages = computed(() => chat.current?.messages ?? []);

async function scrollToBottom() {
  await nextTick();
  scrollEl.value?.scrollTo({ top: scrollEl.value.scrollHeight, behavior: "smooth" });
}

watch(
  () => route.params.conversationId,
  async (id) => {
    if (id) {
      await chat.open(Number(id));
    } else {
      chat.reset();
    }
    scrollToBottom();
  },
  { immediate: true }
);

watch(messages, scrollToBottom, { deep: true });

onMounted(() => {
  chat.refreshLlmStatus();
});

async function handleSubmit(text: string) {
  const wasNew = !chat.current?.id;
  await chat.send(text);
  // 如果是新对话,流式过程中 store 已经把 current.id 改成真实 id,这里同步到 URL
  if (wasNew && chat.current?.id) {
    router.replace({ name: "chat", params: { conversationId: String(chat.current.id) } });
  }
}

const examples = [
  "每天 09:00 把销售表近 24 小时新增的订单汇总发到运维群",
  "看看「产品需求」表上现在有哪些自动化在跑",
  "把刚才那个早报改成每天 10 点",
];
</script>

<template>
  <div class="flex h-full w-full">
    <ConversationList />

    <div class="flex-1 h-full flex flex-col">
      <!-- 顶部条 -->
      <div class="h-14 px-6 flex items-center shrink-0 gap-3">
        <div class="text-title text-ink-900 truncate flex-1">
          {{ chat.current?.title ?? "新对话" }}
        </div>
        <div v-if="chat.llmConfigured === false"
             class="text-caption text-gold-500 glass-flat px-2.5 py-1 rounded-md">
          LLM 未配置 · 当前走 Mock
        </div>
        <div v-else-if="chat.llmConfigured"
             class="text-caption text-success glass-flat px-2.5 py-1 rounded-md">
          ● 智能体已就绪
        </div>
      </div>

      <!-- 消息流 / 空状态 -->
      <div ref="scrollEl" class="flex-1 overflow-y-auto px-6 py-2">
        <div
          v-if="!messages.length"
          class="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto"
        >
          <div class="w-14 h-14 rounded-xl bg-brand-500 flex items-center justify-center mb-5
                      shadow-[0_16px_40px_rgba(79,70,229,0.35)]">
            <Sparkles class="w-7 h-7 text-white" />
          </div>
          <div class="text-display text-ink-900 mb-2">
            描述一下,我来搭工作流
          </div>
          <p class="text-body text-ink-500 mb-8">
            用自然语言告诉我触发条件和要做的动作。
            我会生成一份草稿放进
            <span class="text-gradient-brand font-semibold">草稿箱</span>,
            你可以在画布上二次编辑后再应用到飞书。
          </p>

          <div class="grid grid-cols-1 gap-2 w-full">
            <button
              v-for="(ex, i) in examples"
              :key="i"
              class="glass-flat text-left px-4 py-2.5 rounded-md text-body text-ink-700
                     hover:bg-white/85 transition duration-200 ease-out-quart"
              @click="handleSubmit(ex)"
            >
              {{ ex }}
            </button>
          </div>
        </div>

        <div v-else class="space-y-5 max-w-3xl mx-auto py-4">
          <MessageBubble v-for="m in messages" :key="m.id" :message="m" />
        </div>
      </div>

      <ChatInput :loading="chat.sending" @submit="handleSubmit" />
    </div>
  </div>
</template>
