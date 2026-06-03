<script setup lang="ts">
import { computed } from "vue";
import { Bot, User } from "lucide-vue-next";

import type { Message } from "@/api/chat";
import DraftCard from "./DraftCard.vue";
import ToolCallChip from "./ToolCallChip.vue";

interface Props {
  message: Message;
}
const props = defineProps<Props>();

const isUser = computed(() => props.message.role === "user");
const isTool = computed(() => props.message.role === "tool");
</script>

<template>
  <!-- 工具消息:细线 chip 一行 -->
  <div v-if="isTool" class="flex gap-3 animate-fade-in pl-11">
    <ToolCallChip
      v-if="message.tool_result"
      :name="message.tool_result.name"
      :ok="message.tool_result.ok"
      :result="message.tool_result.result"
    />
  </div>

  <!-- 用户 / 助手 气泡 -->
  <div v-else class="flex gap-3 animate-rise"
       :class="isUser ? 'flex-row-reverse' : ''">
    <div
      class="w-8 h-8 rounded-md flex items-center justify-center shrink-0"
      :class="isUser
        ? 'bg-brand-500 text-white shadow-[0_4px_14px_rgba(79,70,229,0.28)]'
        : 'glass-flat text-ink-700'"
    >
      <User v-if="isUser" class="w-4 h-4" />
      <Bot v-else class="w-4 h-4" />
    </div>

    <div class="max-w-[68%] flex flex-col gap-2"
         :class="isUser ? 'items-end' : 'items-start'">
      <!-- 文本气泡:空且流式中 → 显示打字光标 -->
      <div
        v-if="message.content || !message.streaming || (message.tool_calls?.length ?? 0) === 0"
        class="px-4 py-3 rounded-lg whitespace-pre-wrap break-words text-body relative"
        :class="isUser
          ? 'bg-brand-500 text-white shadow-[0_8px_24px_rgba(79,70,229,0.20)] rounded-tr-sm'
          : 'glass rounded-tl-sm'"
      >
        <template v-if="!message.content && message.streaming">
          <span class="inline-flex gap-1 items-center">
            <span class="w-1.5 h-1.5 rounded-full bg-ink-400 animate-pulse" />
            <span class="w-1.5 h-1.5 rounded-full bg-ink-400 animate-pulse [animation-delay:120ms]" />
            <span class="w-1.5 h-1.5 rounded-full bg-ink-400 animate-pulse [animation-delay:240ms]" />
          </span>
        </template>
        <template v-else>
          {{ message.content }}
          <span v-if="message.streaming"
                class="inline-block w-1 h-3.5 align-text-bottom ml-0.5 bg-ink-700 animate-pulse" />
        </template>
      </div>

      <!-- 工具调用 chip(还没有结果时显示 in-progress)-->
      <div v-if="!isUser && message.tool_calls?.length" class="w-full space-y-1">
        <ToolCallChip
          v-for="tc in message.tool_calls"
          :key="tc.id"
          :name="tc.function.name"
          :args-raw="tc.function.arguments"
          :pending="true"
        />
      </div>

      <DraftCard
        v-if="!isUser && message.draft_id"
        :draft-id="message.draft_id"
        :message-id="message.id"
      />
    </div>
  </div>
</template>
