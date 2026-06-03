<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  Workflow,
  Pencil,
  Zap,
  X,
  CalendarClock,
  Send,
  Database,
  Globe,
  GitBranch,
  AtSign,
  PencilLine,
} from "lucide-vue-next";

import { workflowsApi, type WorkflowDetail, type WorkflowNode } from "@/api/workflows";
import { useToastStore } from "@/stores/toast";

interface Props {
  draftId: number;
  messageId: number;
}
const props = defineProps<Props>();

const router = useRouter();
const toast = useToastStore();
const draft = ref<WorkflowDetail | null>(null);
const loading = ref(true);
const dismissed = ref(false);
const applying = ref(false);

onMounted(async () => {
  try {
    draft.value = await workflowsApi.get(props.draftId);
  } finally {
    loading.value = false;
  }
});

function iconFor(type: string) {
  if (type.startsWith("trigger.schedule")) return CalendarClock;
  if (type.startsWith("trigger.bot_mention")) return AtSign;
  if (type.startsWith("trigger.bitable")) return Database;
  if (type.startsWith("action.bitable_update")) return PencilLine;
  if (type.startsWith("action.send_message")) return Send;
  if (type.startsWith("action.bitable")) return Database;
  if (type.startsWith("action.http")) return Globe;
  if (type.startsWith("condition")) return GitBranch;
  return Workflow;
}

function labelFor(type: string) {
  const map: Record<string, string> = {
    "trigger.schedule": "定时触发",
    "trigger.bitable_change": "表格变更",
    "trigger.bot_mention": "@机器人触发",
    "action.bitable_query": "查询表格",
    "action.bitable_update": "修改表格（多维表格）",
    "action.send_message": "发送消息",
    "action.http": "HTTP 请求",
    "condition.if": "条件分支",
  };
  return map[type] ?? type;
}

function previewConfig(node: WorkflowNode) {
  const c = node.config ?? {};
  if (node.type === "trigger.schedule") return c.cron ?? "—";
  if (node.type === "trigger.bot_mention") return `${c.bot_id ?? "default"} · ${c.keyword ? `关键词: ${c.keyword}` : (c.chat_type ?? "全部")}`;
  if (node.type === "action.send_message") return c.chat_id ?? "—";
  if (node.type === "action.bitable_query") return c.table_id ?? "—";
  if (node.type === "action.bitable_update") return `${c.table_id ?? "—"} · ${c.record_id ?? "—"}`;
  if (node.type === "action.http") return `${c.method ?? "GET"} ${c.url ?? "—"}`;
  return "";
}

function openEditor() {
  if (!draft.value) return;
  router.push({ name: "workflow-editor", params: { id: String(draft.value.id) } });
}

async function applyNow() {
  if (!draft.value || applying.value) return;
  applying.value = true;
  try {
    const r = await workflowsApi.apply(draft.value.id);
    toast.ok(`已应用 · 下一次运行 ${r.next_run ?? "无"}`);
    draft.value = await workflowsApi.get(draft.value.id);
  } catch (e: any) {
    toast.err(e?.response?.data?.detail ?? "应用失败");
  } finally {
    applying.value = false;
  }
}

function dismiss() {
  dismissed.value = true;
}
</script>

<template>
  <div
    v-if="!dismissed"
    class="glass-strong rounded-lg p-4 w-full max-w-[480px] animate-rise"
  >
    <div v-if="loading" class="text-caption text-ink-400">加载草稿中…</div>

    <template v-else-if="draft">
      <div class="flex items-start gap-3 mb-3">
        <div class="w-9 h-9 rounded-md bg-gradient-to-br from-brand-500 to-brand-400
                    flex items-center justify-center shrink-0
                    shadow-[0_8px_20px_rgba(79,70,229,0.28)]">
          <Workflow class="w-[18px] h-[18px] text-white" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-title text-ink-900 truncate">{{ draft.name }}</div>
          <div class="text-caption">{{ draft.description }}</div>
        </div>
        <button
          class="text-ink-400 hover:text-ink-700 transition"
          @click="dismiss"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- 节点序列预览 -->
      <div class="space-y-2 mb-4">
        <div
          v-for="node in draft.graph.nodes"
          :key="node.id"
          class="flex items-center gap-3 px-3 py-2 rounded-md bg-white/50 border border-white/70"
        >
          <component
            :is="iconFor(node.type)"
            class="w-4 h-4 shrink-0"
            :class="node.type.startsWith('trigger') ? 'text-brand-500'
                  : node.type.startsWith('condition') ? 'text-gold-500'
                  : 'text-ink-700'"
          />
          <div class="flex-1 min-w-0">
            <div class="text-body text-ink-900 truncate">{{ labelFor(node.type) }}</div>
            <div class="text-caption truncate">{{ previewConfig(node) }}</div>
          </div>
        </div>
      </div>

      <div class="flex gap-2">
        <button class="btn-secondary flex-1" @click="openEditor">
          <Pencil class="w-3.5 h-3.5" />
          进草稿箱编辑
        </button>
        <button
          class="btn-primary flex-1"
          :disabled="applying || draft.status === 'applied'"
          @click="applyNow"
        >
          <Zap class="w-3.5 h-3.5" />
          {{ draft.status === "applied" ? "已应用" : applying ? "应用中…" : "直接应用" }}
        </button>
      </div>
    </template>

    <div v-else class="text-caption text-danger">草稿加载失败</div>
  </div>
</template>
