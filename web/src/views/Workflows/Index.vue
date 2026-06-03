<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  Plus,
  Workflow,
  Trash2,
  Copy,
  CheckCircle2,
  Archive,
  PencilLine,
} from "lucide-vue-next";

import { useWorkflowsStore } from "@/stores/workflows";
import { workflowsApi, type WorkflowStatus } from "@/api/workflows";

const router = useRouter();
const store = useWorkflowsStore();

const tab = ref<"all" | WorkflowStatus>("all");
const filtered = computed(() => store.list);

async function reload() {
  await store.loadList(tab.value === "all" ? undefined : tab.value);
}

watch(tab, reload);

onMounted(reload);

async function createBlank() {
  const detail = await store.create("新建工作流");
  router.push({ name: "workflow-editor", params: { id: String(detail.id) } });
}

function open(id: number) {
  router.push({ name: "workflow-editor", params: { id: String(id) } });
}

async function duplicate(id: number, e: Event) {
  e.stopPropagation();
  await workflowsApi.duplicate(id);
  await store.loadList();
}

async function remove(id: number, e: Event) {
  e.stopPropagation();
  if (!confirm("删除这个草稿?")) return;
  await store.remove(id);
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

const tabs = [
  { id: "all", label: "全部" },
  { id: "draft", label: "草稿" },
  { id: "applied", label: "已应用" },
  { id: "archived", label: "已归档" },
] as const;

function statusBadge(s: WorkflowStatus) {
  if (s === "applied") return { label: "已应用", color: "text-success", icon: CheckCircle2 };
  if (s === "archived") return { label: "已归档", color: "text-ink-400", icon: Archive };
  return { label: "草稿", color: "text-brand-500", icon: PencilLine };
}
</script>

<template>
  <div class="flex-1 h-full overflow-y-auto px-8 py-6">
    <div class="max-w-6xl mx-auto">
      <!-- 顶部 -->
      <div class="flex items-end justify-between mb-7">
        <div>
          <div class="text-display text-ink-900">工作流草稿箱</div>
          <p class="text-body text-ink-500 mt-1.5">
            所有由对话生成或手动新建的工作流都在这。改完点【应用】才会真到飞书。
          </p>
        </div>
        <button class="btn-primary" @click="createBlank">
          <Plus class="w-4 h-4" />
          新建工作流
        </button>
      </div>

      <!-- Tab -->
      <div class="glass-flat rounded-md inline-flex p-1 mb-5">
        <button
          v-for="t in tabs"
          :key="t.id"
          class="px-4 h-8 rounded text-body transition duration-200 ease-out-quart"
          :class="tab === t.id
            ? 'bg-brand-500 text-white shadow-[0_4px_12px_rgba(79,70,229,0.22)]'
            : 'text-ink-700 hover:bg-white/85'"
          @click="tab = t.id"
        >
          {{ t.label }}
        </button>
      </div>

      <!-- 列表 -->
      <div v-if="store.loading" class="text-caption text-ink-400">加载中…</div>

      <div
        v-else-if="!filtered.length"
        class="glass rounded-lg p-12 text-center"
      >
        <Workflow class="w-10 h-10 mx-auto text-ink-300 mb-3" />
        <div class="text-title text-ink-700 mb-1.5">还没有工作流</div>
        <p class="text-body text-ink-500 mb-5">
          回对话页用一句话描述需求,或在这里手动新建。
        </p>
        <button class="btn-primary mx-auto" @click="createBlank">
          <Plus class="w-4 h-4" />
          新建空白工作流
        </button>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <div
          v-for="wf in filtered"
          :key="wf.id"
          class="glass rounded-lg p-5 cursor-pointer
                 transition duration-200 ease-out-quart
                 hover:-translate-y-0.5 hover:shadow-glass-strong
                 group"
          @click="open(wf.id)"
        >
          <div class="flex items-start gap-3 mb-3">
            <div class="w-9 h-9 rounded-md bg-gradient-to-br from-brand-500 to-brand-400
                        flex items-center justify-center shrink-0
                        shadow-[0_6px_18px_rgba(79,70,229,0.25)]">
              <Workflow class="w-[18px] h-[18px] text-white" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-title text-ink-900 truncate">{{ wf.name }}</div>
              <div class="text-caption truncate">
                {{ wf.description ?? '无描述' }}
              </div>
            </div>
          </div>

          <div class="flex items-center justify-between">
            <div
              class="flex items-center gap-1.5 text-caption"
              :class="statusBadge(wf.status).color"
            >
              <component :is="statusBadge(wf.status).icon" class="w-3.5 h-3.5" />
              {{ statusBadge(wf.status).label }}
              <span class="text-ink-400 ml-2">· {{ relativeTime(wf.updated_at) }}</span>
            </div>

            <div class="flex items-center gap-1
                        opacity-0 group-hover:opacity-100 transition duration-200">
              <button
                class="w-7 h-7 rounded text-ink-500 hover:bg-white/85 hover:text-ink-900
                       flex items-center justify-center"
                title="复制"
                @click="duplicate(wf.id, $event)"
              >
                <Copy class="w-3.5 h-3.5" />
              </button>
              <button
                class="w-7 h-7 rounded text-ink-500 hover:bg-white/85 hover:text-danger
                       flex items-center justify-center"
                title="删除"
                @click="remove(wf.id, $event)"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
