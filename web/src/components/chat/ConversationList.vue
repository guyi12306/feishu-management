<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Plus, Trash2, MessageSquare, Pencil, Check, X } from "lucide-vue-next";

import { useChatStore } from "@/stores/chat";
import { useToastStore } from "@/stores/toast";

const chat = useChatStore();
const toast = useToastStore();
const route = useRoute();
const router = useRouter();

const editingId = ref<number | null>(null);
const editingTitle = ref("");

onMounted(() => {
  chat.loadList();
});

async function startEdit(id: number, title: string, e: Event) {
  e.stopPropagation();
  editingId.value = id;
  editingTitle.value = title;
  await nextTick();
  const el = document.querySelector<HTMLInputElement>(`[data-edit-input="${id}"]`);
  el?.select();
}

async function commitEdit(id: number) {
  const newTitle = editingTitle.value.trim();
  if (!newTitle) {
    editingId.value = null;
    return;
  }
  try {
    await chat.rename(id, newTitle);
    toast.ok("已重命名");
  } catch (e: any) {
    toast.err(e?.response?.data?.detail ?? "重命名失败");
  } finally {
    editingId.value = null;
  }
}

function cancelEdit() {
  editingId.value = null;
}

function open(id: number) {
  router.push({ name: "chat", params: { conversationId: String(id) } });
}

function newConv() {
  chat.reset();
  router.push({ name: "chat" });
}

async function remove(id: number, e: Event) {
  e.stopPropagation();
  if (!confirm("删除这个会话?")) return;
  await chat.removeConversation(id);
  if (route.params.conversationId === String(id)) {
    router.replace({ name: "chat" });
  }
}

function relativeTime(iso: string) {
  const d = new Date(iso.replace(" ", "T") + "Z");
  const diffSec = (Date.now() - d.getTime()) / 1000;
  if (diffSec < 60) return "刚刚";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`;
  if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)} 天前`;
  return d.toLocaleDateString();
}
</script>

<template>
  <div class="w-[260px] shrink-0 h-full flex flex-col p-3 gap-3">
    <button
      class="btn-primary w-full"
      @click="newConv"
    >
      <Plus class="w-4 h-4" />
      <span>新对话</span>
    </button>

    <div class="flex-1 overflow-y-auto space-y-1.5 no-scrollbar -mx-1 px-1">
      <div
        v-if="!chat.conversations.length && !chat.loadingList"
        class="text-caption text-ink-400 text-center mt-12"
      >
        还没有会话
      </div>

      <div
        v-for="conv in chat.conversations"
        :key="conv.id"
        class="group glass-flat px-3 py-2.5 rounded-md cursor-pointer
               transition duration-200 ease-out-quart
               hover:bg-white/85"
        :class="String(conv.id) === route.params.conversationId
                  ? 'ring-2 ring-brand-400/60 bg-white/90' : ''"
        @click="editingId !== conv.id && open(conv.id)"
      >
        <div class="flex items-start gap-2">
          <MessageSquare class="w-4 h-4 text-ink-500 mt-0.5 shrink-0" />
          <div class="flex-1 min-w-0">
            <template v-if="editingId === conv.id">
              <input
                :data-edit-input="conv.id"
                v-model="editingTitle"
                class="w-full bg-white/90 rounded px-1.5 py-0.5 text-body text-ink-900
                       outline-none border border-brand-300 focus:border-brand-500"
                @click.stop
                @keydown.enter="commitEdit(conv.id)"
                @keydown.esc="cancelEdit"
                @blur="commitEdit(conv.id)"
              />
            </template>
            <template v-else>
              <div class="text-body text-ink-900 truncate">{{ conv.title }}</div>
              <div class="text-caption">{{ relativeTime(conv.updated_at) }}</div>
            </template>
          </div>
          <div v-if="editingId !== conv.id"
               class="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition duration-150">
            <button
              class="text-ink-400 hover:text-ink-900 w-6 h-6 flex items-center justify-center"
              title="重命名"
              @click="startEdit(conv.id, conv.title, $event)"
            >
              <Pencil class="w-3 h-3" />
            </button>
            <button
              class="text-ink-400 hover:text-danger w-6 h-6 flex items-center justify-center"
              title="删除"
              @click="remove(conv.id, $event)"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
