<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  VueFlow,
  useVueFlow,
  type Connection,
} from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import { Controls } from "@vue-flow/controls";
import { MiniMap } from "@vue-flow/minimap";
import {
  ArrowLeft,
  Save,
  Zap,
  ZapOff,
  Activity,
  Loader2,
  CheckCircle2,
} from "lucide-vue-next";

import CanvasNode from "@/components/workflow/CanvasNode.vue";
import NodePalette from "@/components/workflow/NodePalette.vue";
import Inspector from "@/components/workflow/Inspector.vue";
import RunsDrawer from "@/components/workflow/RunsDrawer.vue";
import { useWorkflowsStore } from "@/stores/workflows";
import { workflowsApi } from "@/api/workflows";
import { settingsApi, type FeishuBot } from "@/api/settings";
import { useToastStore } from "@/stores/toast";

const toast = useToastStore();

import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";
import "@vue-flow/controls/dist/style.css";
import "@vue-flow/minimap/dist/style.css";

const route = useRoute();
const router = useRouter();
const store = useWorkflowsStore();

const id = ref<number>(Number(route.params.id));

const flowNodes = ref<any[]>([]);
const flowEdges = ref<any[]>([]);
const selectedNodeId = ref<string | null>(null);

const saving = ref(false);
const savedAt = ref<number | null>(null);
const applying = ref(false);
const runsOpen = ref(false);
const paletteCollapsed = ref(false);
const inspectorOpen = ref(false);
const customNodeTypes = { custom: CanvasNode as any };
const bots = ref<FeishuBot[]>([]);

// 选中节点时自动打开 Inspector
watch(selectedNodeId, (v) => {
  if (v) inspectorOpen.value = true;
});

const {
  onConnect,
  addEdges,
  addNodes,
  project,
  removeNodes,
  removeEdges,
  getSelectedNodes,
  getSelectedEdges,
  viewport,
} = useVueFlow();

const isApplied = computed(() => store.current?.status === "applied");
const selectedBotValue = computed(() =>
  store.current?.bot_id === "default" ? "" : store.current?.bot_id ?? ""
);
const selectableBots = computed(() => bots.value.filter((bot) => !bot.is_default));

const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null;
  const n = flowNodes.value.find((x) => x.id === selectedNodeId.value);
  if (!n) return null;
  return {
    id: n.id,
    nodeType: (n.data as any)?.nodeType ?? "",
    config: ((n.data as any)?.config ?? {}) as Record<string, any>,
  };
});

function localizeBitableEvent(value: any): string {
  const key = String(value ?? "").trim().toLowerCase();
  const map: Record<string, string> = {
    create: "新增",
    add: "新增",
    insert: "新增",
    update: "更新",
    edit: "更新",
    modify: "更新",
    delete: "删除",
    remove: "删除",
    新增: "新增",
    新建: "新增",
    创建: "新增",
    更新: "更新",
    修改: "更新",
    编辑: "更新",
    删除: "删除",
    移除: "删除",
  };
  return map[key] ?? "新增";
}

function normalizeNodeConfig(nodeType: string, config: Record<string, any> = {}) {
  if (nodeType !== "trigger.bitable_change") return { ...config };
  return { ...config, event: localizeBitableEvent(config.event) };
}

function toFlow(graph: { nodes: any[]; edges: any[] }) {
  flowNodes.value = (graph.nodes ?? []).map((n) => ({
    id: n.id,
    type: "custom",
    position: n.position ?? { x: 0, y: 0 },
    data: { nodeType: n.type, config: normalizeNodeConfig(n.type, n.config ?? {}) },
  }));
  flowEdges.value = (graph.edges ?? []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: false,
    type: "smoothstep",
    style: { stroke: "#4F46E5", strokeWidth: 1.6 },
  }));
}

function toGraph() {
  return {
    nodes: flowNodes.value.map((n) => ({
      id: n.id,
      type: (n.data as any).nodeType,
      position: { x: n.position.x, y: n.position.y },
      config: normalizeNodeConfig(
        (n.data as any).nodeType,
        (n.data as any).config ?? {}
      ),
    })),
    edges: flowEdges.value.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
    })),
    viewport: { x: viewport.value.x, y: viewport.value.y, zoom: viewport.value.zoom },
  };
}

// ────── 自动保存(debounce 800ms) ──────
let saveTimer: ReturnType<typeof setTimeout> | null = null;
function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(doSave, 800);
}

async function doSave() {
  if (!store.current) return;
  saving.value = true;
  try {
    await store.update(store.current.id, { graph: toGraph() as any });
    savedAt.value = Date.now();
  } finally {
    saving.value = false;
  }
}

async function saveNow() {
  if (saveTimer) {
    clearTimeout(saveTimer);
    saveTimer = null;
  }
  await doSave();
}

watch([flowNodes, flowEdges], scheduleSave, { deep: true });

// ────── 加载草稿 ──────
watch(
  () => route.params.id,
  async (v) => {
    if (!v) return;
    id.value = Number(v);
    await store.open(id.value);
    if (store.current) toFlow(store.current.graph);
  },
  { immediate: true }
);

onMounted(() => {
  store.loadNodeTypes();
  loadBots();
});

async function loadBots() {
  try {
    bots.value = await settingsApi.listFeishuBots();
  } catch {
    bots.value = [];
  }
}

// ────── 名字双向 ──────
async function saveName() {
  if (!store.current) return;
  await store.update(store.current.id, { name: store.current.name });
}

async function saveBotId(e: Event) {
  if (!store.current) return;
  const value = (e.target as HTMLSelectElement).value || null;
  await store.update(store.current.id, { bot_id: value });
}

// ────── 拖入新节点 ──────
function onDrop(e: DragEvent) {
  const type = e.dataTransfer?.getData("application/vnd.lark-node-type");
  if (!type) return;
  e.preventDefault();
  const target = e.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const pos = project({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  const prefix = type.startsWith("trigger.") ? "t"
              : type.startsWith("condition.") ? "c" : "a";
  const newId = `${prefix}${Math.floor(Math.random() * 9000) + 1000}`;
  addNodes([
    {
      id: newId,
      type: "custom",
      position: pos,
      data: { nodeType: type, config: defaultConfig(type) },
    },
  ]);
  selectedNodeId.value = newId;
}

function onDragOver(e: DragEvent) {
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
}

function defaultConfig(type: string): Record<string, any> {
  if (type === "trigger.schedule") return { cron: "0 9 * * *", tz: "Asia/Shanghai" };
  if (type === "trigger.bitable_change") return { event: "新增" };
  if (type === "trigger.bot_mention") return { chat_type: "全部" };
  if (type === "action.http") return { method: "GET" };
  return {};
}

// ────── 连线 ──────
onConnect((conn: Connection) => {
  if (!conn.source || !conn.target) return;
  const edgeId = `e${conn.source}-${conn.target}`;
  addEdges([
    {
      id: edgeId,
      source: conn.source,
      target: conn.target,
      type: "smoothstep",
      style: { stroke: "#4F46E5", strokeWidth: 1.6 },
    },
  ]);
});

// ────── 选中 ──────
function onNodeClick(payload: any) {
  const node = payload?.node ?? payload;
  if (node?.id) selectedNodeId.value = node.id;
}

function onEdgeClick(_payload: any) {
  // 点连线时取消节点选中,让 Inspector 不抢焦点
  selectedNodeId.value = null;
}

function onPaneClick() {
  selectedNodeId.value = null;
  inspectorOpen.value = false;
}

// ────── Inspector 改 ──────
function updateNodeConfig(nodeId: string, config: Record<string, any>) {
  const n = flowNodes.value.find((x) => x.id === nodeId);
  if (!n) return;
  (n.data as any).config = normalizeNodeConfig((n.data as any).nodeType, config);
  // 强制响应
  flowNodes.value = [...flowNodes.value];
}

function removeNode(nodeId: string) {
  removeNodes([nodeId]);
  // 同时把相关 edges 拿掉
  const toRemove = flowEdges.value
    .filter((e) => e.source === nodeId || e.target === nodeId)
    .map((e) => e.id);
  if (toRemove.length) removeEdges(toRemove);
  if (selectedNodeId.value === nodeId) selectedNodeId.value = null;
}

// ────── 应用 / 撤销 ──────
async function toggleApply() {
  if (!store.current) return;
  applying.value = true;
  try {
    await saveNow();
    if (isApplied.value) {
      await workflowsApi.unapply(store.current.id);
      toast.ok("已撤销应用");
    } else {
      const r = await workflowsApi.apply(store.current.id);
      toast.ok(`已应用 · 下次运行:${r.next_run ?? "无"}`);
    }
    await store.open(store.current.id);
  } catch (e: any) {
    toast.err(e?.response?.data?.detail ?? e?.message ?? "操作失败");
  } finally {
    applying.value = false;
  }
}

// ────── 键盘 Del/Backspace 兜底 ──────
// Vue Flow 自带 delete-key-code 在某些边缘情况下不触发,这里做兜底
function onWindowKeyDown(e: KeyboardEvent) {
  if (e.key !== "Delete" && e.key !== "Backspace") return;
  const t = e.target as HTMLElement | null;
  // 输入框 / 富文本里不要劫持
  const tag = t?.tagName ?? "";
  if (tag === "INPUT" || tag === "TEXTAREA" || t?.isContentEditable) return;

  const nodes = (typeof getSelectedNodes === "function"
    ? getSelectedNodes
    : (getSelectedNodes as any)) as any;
  const edges = (typeof getSelectedEdges === "function"
    ? getSelectedEdges
    : (getSelectedEdges as any)) as any;
  const selNodes = (nodes?.value ?? nodes ?? []) as Array<{ id: string }>;
  const selEdges = (edges?.value ?? edges ?? []) as Array<{ id: string }>;

  const nodeIds = selNodes.map((n) => n.id);
  const edgeIds = selEdges.map((ed) => ed.id);
  if (!nodeIds.length && !edgeIds.length) return;

  if (nodeIds.length) {
    removeNodes(nodeIds);
    // 顺手把和已删节点关联的边也清掉
    const drop = flowEdges.value
      .filter((ed) => nodeIds.includes(ed.source) || nodeIds.includes(ed.target))
      .map((ed) => ed.id);
    if (drop.length) removeEdges(drop);
    if (selectedNodeId.value && nodeIds.includes(selectedNodeId.value)) {
      selectedNodeId.value = null;
    }
  }
  if (edgeIds.length) {
    removeEdges(edgeIds);
  }
  e.preventDefault();
}

onMounted(() => {
  window.addEventListener("keydown", onWindowKeyDown);
});

import { onBeforeUnmount } from "vue";
onBeforeUnmount(() => {
  window.removeEventListener("keydown", onWindowKeyDown);
});

// 离开页面前 flush
import { onBeforeRouteLeave } from "vue-router";
onBeforeRouteLeave(async () => {
  await saveNow();
});

const savedLabel = computed(() => {
  if (saving.value) return "保存中…";
  if (savedAt.value) {
    const dt = (Date.now() - savedAt.value) / 1000;
    if (dt < 5) return "已保存";
    if (dt < 60) return `${Math.floor(dt)} 秒前保存`;
    return `${Math.floor(dt / 60)} 分钟前保存`;
  }
  return "";
});
</script>

<template>
  <div class="flex-1 h-full flex flex-col">
    <!-- 顶部 Toolbar -->
    <div class="h-14 px-5 flex items-center gap-3 shrink-0 border-b border-white/40
                glass-flat !rounded-none">
      <button class="btn-ghost !h-9 !px-2" @click="router.push({ name: 'workflows' })">
        <ArrowLeft class="w-4 h-4" />
      </button>

      <input
        v-if="store.current"
        v-model="store.current.name"
        class="bg-transparent text-title font-semibold flex-1 max-w-md px-2 outline-none
               border-b border-transparent hover:border-white/80 focus:border-brand-400"
        @blur="saveName"
      />
      <div v-else class="text-title text-ink-400">加载中…</div>

      <div class="text-caption text-ink-400 ml-1 flex items-center gap-1">
        <Loader2 v-if="saving" class="w-3 h-3 animate-spin" />
        <CheckCircle2 v-else-if="savedAt" class="w-3 h-3 text-success" />
        {{ savedLabel }}
      </div>

      <div class="flex-1" />

      <select
        v-if="store.current"
        class="input !h-9 !w-[180px] text-caption"
        :value="selectedBotValue"
        title="执行机器人"
        @change="saveBotId"
      >
        <option value="">默认机器人</option>
        <option v-for="bot in selectableBots" :key="bot.id" :value="bot.id">
          {{ bot.name }}
        </option>
      </select>

      <!-- 状态徽章 -->
      <span v-if="isApplied"
            class="text-caption text-success glass-flat px-2.5 py-1 rounded">
        ● 已应用
      </span>
      <span v-else
            class="text-caption text-ink-500 glass-flat px-2.5 py-1 rounded">
        草稿
      </span>

      <button class="btn-secondary" @click="runsOpen = true">
        <Activity class="w-3.5 h-3.5" />
        执行历史
      </button>

      <button class="btn-secondary" :disabled="saving" @click="saveNow">
        <Save class="w-3.5 h-3.5" />
        立即保存
      </button>

      <button
        :class="isApplied ? 'btn-secondary !text-danger' : 'btn-primary'"
        :disabled="applying"
        @click="toggleApply"
      >
        <Loader2 v-if="applying" class="w-3.5 h-3.5 animate-spin" />
        <ZapOff v-else-if="isApplied" class="w-3.5 h-3.5" />
        <Zap v-else class="w-3.5 h-3.5" />
        {{ isApplied ? "撤销应用" : "应用到飞书" }}
      </button>
    </div>

    <!-- 主体:左 Palette + Canvas;Inspector / Runs 抽屉浮在右侧 -->
    <div class="flex-1 flex min-h-0">
      <!-- NodePalette -->
      <div
        class="glass !rounded-none border-r border-white/40 min-h-0 min-w-0 overflow-hidden shrink-0"
        :style="{ width: paletteCollapsed ? '48px' : '240px' }"
      >
        <NodePalette
          v-model:collapsed="paletteCollapsed"
          :registry="store.nodeTypes"
        />
      </div>

      <!-- Canvas -->
      <div class="flex-1 relative min-w-0" @drop="onDrop" @dragover="onDragOver">
        <!-- 交互提示 -->
        <div class="absolute top-3 left-1/2 -translate-x-1/2 z-10 pointer-events-none
                    glass-flat rounded-md px-3 py-1.5 text-caption text-ink-700
                    flex items-center gap-3">
          <span><b class="text-ink-900">左键</b> 选中/框选</span>
          <span class="text-ink-300">·</span>
          <span><b class="text-ink-900">中键</b> 拖动画布</span>
          <span class="text-ink-300">·</span>
          <span><b class="text-ink-900">Del</b> 删除选中</span>
        </div>

        <VueFlow
          v-model:nodes="flowNodes"
          v-model:edges="flowEdges"
          :default-viewport="{ zoom: 1 }"
          :min-zoom="0.4"
          :max-zoom="1.6"
          :node-types="customNodeTypes"
          :select-nodes-on-drag="false"
          :pan-on-drag="[1]"
          :selection-on-drag="true"
          :pan-on-scroll="false"
          :zoom-on-scroll="true"
          :delete-key-code="['Delete', 'Backspace']"
          :selection-key-code="null"
          :multi-selection-key-code="['Shift', 'Control', 'Meta']"
          fit-view-on-init
          class="w-full h-full"
          @node-click="onNodeClick"
          @edge-click="onEdgeClick"
          @pane-click="onPaneClick"
        >
          <Background pattern-color="rgba(15,20,25,0.12)" :gap="24" />
          <Controls position="bottom-right" />
          <MiniMap
            position="bottom-left"
            pannable
            :node-color="(n) => {
              const t = (n.data as any)?.nodeType ?? '';
              if (t.startsWith('trigger.')) return '#4F46E5';
              if (t.startsWith('condition.')) return '#D4A056';
              return '#6B7280';
            }"
          />
        </VueFlow>
      </div>
    </div>

    <!-- Inspector 抽屉(浮于右侧) -->
    <Inspector
      :registry="store.nodeTypes"
      :node="selectedNode"
      :open="inspectorOpen && !runsOpen"
      @update="updateNodeConfig"
      @remove="(id) => { removeNode(id); inspectorOpen = false; }"
      @close="inspectorOpen = false; selectedNodeId = null;"
    />

    <RunsDrawer
      v-if="store.current"
      :workflow-id="store.current.id"
      :open="runsOpen"
      @close="runsOpen = false"
      @run-now="store.current && store.open(store.current.id)"
    />
  </div>
</template>

<style>
.vue-flow__handle { width: 10px !important; height: 10px !important; }
.vue-flow__minimap {
  background: rgba(255,255,255,0.65) !important;
  border-radius: 10px !important;
  box-shadow: 0 8px 24px rgba(15,20,25,0.08);
}
.vue-flow__controls {
  background: rgba(255,255,255,0.65);
  backdrop-filter: blur(12px);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(15,20,25,0.08);
  padding: 4px;
}
.vue-flow__controls-button {
  background: transparent !important;
  border: none !important;
}

/* 连线选中态:换成暗金,加粗 + 光晕,跟普通连线区分 */
.vue-flow__edge.selected .vue-flow__edge-path,
.vue-flow__edge:focus .vue-flow__edge-path,
.vue-flow__edge:focus-visible .vue-flow__edge-path {
  stroke: #D4A056 !important;
  stroke-width: 2.6 !important;
  filter: drop-shadow(0 0 6px rgba(212, 160, 86, 0.55));
}

/* 拖动框选时的虚线选区 */
.vue-flow__selection,
.vue-flow__nodesselection-rect {
  background: rgba(79, 70, 229, 0.08) !important;
  border: 1.5px dashed #4F46E5 !important;
  border-radius: 6px !important;
}
</style>
