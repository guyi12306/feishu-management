<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  X,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronRight,
  Zap,
} from "lucide-vue-next";

import client from "@/api/client";

interface RunSummary {
  id: number;
  status: string;
  trigger: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  error: string | null;
}

interface RunDetail extends RunSummary {
  log: {
    node_id: string;
    node_type: string;
    status: string;
    output?: any;
    error?: string | null;
    duration_ms: number;
  }[];
}

interface Props {
  workflowId: number;
  open: boolean;
}
const props = defineProps<Props>();
const emit = defineEmits<{ (e: "close"): void; (e: "run-now"): void }>();

const list = ref<RunSummary[]>([]);
const detail = ref<RunDetail | null>(null);
const loading = ref(false);
const running = ref(false);

async function loadList() {
  loading.value = true;
  try {
    const { data } = await client.get(`/workflows/${props.workflowId}/runs`);
    list.value = data;
  } finally {
    loading.value = false;
  }
}

async function openDetail(id: number) {
  const { data } = await client.get(`/workflows/${props.workflowId}/runs/${id}`);
  detail.value = data;
}

async function runNow() {
  running.value = true;
  try {
    await client.post(`/workflows/${props.workflowId}/run-now`);
    await loadList();
    emit("run-now");
  } finally {
    running.value = false;
  }
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      detail.value = null;
      loadList();
    }
  }
);

function statusIcon(s: string) {
  if (s === "success") return { c: CheckCircle2, cls: "text-success" };
  if (s === "running") return { c: Loader2, cls: "text-brand-500 animate-spin" };
  return { c: XCircle, cls: "text-danger" };
}

function fmtDuration(ms: number | null) {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function fmtTime(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso.replace(" ", "T") + "Z");
  return d.toLocaleString("zh-CN", { hour12: false });
}

function triggerLabel(trigger: string) {
  if (trigger === "manual") return "手动";
  if (trigger === "schedule") return "定时";
  if (trigger === "bitable_change") return "表格变更";
  if (trigger === "bot_mention") return "@机器人";
  return trigger;
}
</script>

<template>
    <div
      v-show="props.open"
      class="fixed top-0 right-0 h-full w-[460px] z-30 glass-strong border-l border-white/60
             shadow-glass-strong flex flex-col"
    >
      <div class="h-14 px-5 flex items-center gap-3 border-b border-white/40">
        <div class="text-title text-ink-900 flex-1">执行历史</div>
        <button class="btn-secondary !h-8" :disabled="running" @click="runNow">
          <Loader2 v-if="running" class="w-3.5 h-3.5 animate-spin" />
          <Zap v-else class="w-3.5 h-3.5" />
          立即执行
        </button>
        <button class="text-ink-500 hover:text-ink-900 w-7 h-7 flex items-center justify-center"
                @click="emit('close')">
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- 主体 -->
      <div class="flex-1 overflow-y-auto">
        <!-- 列表态 -->
        <template v-if="!detail">
          <div v-if="loading" class="text-caption text-ink-400 px-5 py-6">加载中…</div>
          <div v-else-if="!list.length" class="text-caption text-ink-400 px-5 py-6 text-center">
            还没有执行过这个工作流。
          </div>
          <div v-else class="px-3 py-3 space-y-1.5">
            <button
              v-for="r in list"
              :key="r.id"
              class="glass-flat w-full rounded-md px-3 py-2.5 flex items-center gap-3
                     hover:bg-white/85 transition duration-200 ease-out-quart"
              @click="openDetail(r.id)"
            >
              <component
                :is="statusIcon(r.status).c"
                class="w-4 h-4 shrink-0"
                :class="statusIcon(r.status).cls"
              />
              <div class="flex-1 min-w-0 text-left">
                <div class="text-body text-ink-900">
                  #{{ r.id }} · {{ triggerLabel(r.trigger) }}
                </div>
                <div class="text-caption truncate">
                  {{ fmtTime(r.started_at) }} · {{ fmtDuration(r.duration_ms) }}
                </div>
              </div>
              <ChevronRight class="w-3.5 h-3.5 text-ink-400 shrink-0" />
            </button>
          </div>
        </template>

        <!-- 详情态 -->
        <template v-else>
          <div class="px-4 py-3 border-b border-white/40">
            <button class="text-caption text-brand-500 mb-2" @click="detail = null">
              ← 返回列表
            </button>
            <div class="flex items-center gap-2">
              <component
                :is="statusIcon(detail.status).c"
                class="w-4 h-4"
                :class="statusIcon(detail.status).cls"
              />
              <div class="text-title text-ink-900">运行 #{{ detail.id }}</div>
            </div>
            <div class="text-caption mt-1">
              {{ fmtTime(detail.started_at) }} → {{ fmtTime(detail.finished_at) }}
              · {{ fmtDuration(detail.duration_ms) }}
            </div>
            <div v-if="detail.error"
                 class="mt-2 text-caption text-danger glass-flat px-2.5 py-1.5 rounded">
              {{ detail.error }}
            </div>
          </div>

          <div class="px-3 py-3 space-y-2">
            <div
              v-for="entry in detail.log"
              :key="entry.node_id"
              class="glass-flat rounded-md p-3"
            >
              <div class="flex items-center gap-2 mb-1.5">
                <component
                  :is="statusIcon(entry.status === 'ok' ? 'success'
                                : entry.status === 'skipped' ? 'success'
                                : 'failed').c"
                  class="w-3.5 h-3.5"
                  :class="entry.status === 'ok' ? 'text-success'
                        : entry.status === 'skipped' ? 'text-ink-400'
                        : 'text-danger'"
                />
                <span class="text-body text-ink-900 font-medium">{{ entry.node_type }}</span>
                <span class="text-caption text-ink-400">· {{ entry.node_id }}</span>
                <span class="text-caption ml-auto">{{ fmtDuration(entry.duration_ms) }}</span>
              </div>
              <pre v-if="entry.output !== undefined && entry.output !== null"
                   class="text-[11.5px] bg-white/60 rounded p-2 overflow-x-auto max-h-40"
              >{{ JSON.stringify(entry.output, null, 2) }}</pre>
              <div v-if="entry.error" class="text-caption text-danger mt-1">
                {{ entry.error }}
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
</template>
