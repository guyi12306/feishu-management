<script setup lang="ts">
import { computed } from "vue";
import { ChevronsLeft, ChevronsRight } from "lucide-vue-next";

import type { NodeTypeRegistry } from "@/api/workflows";
import { metaOf } from "./nodeMeta";

interface Props {
  registry: NodeTypeRegistry | null;
  collapsed: boolean;
}
const props = defineProps<Props>();
const emit = defineEmits<{ (e: "update:collapsed", v: boolean): void }>();

const grouped = computed(() => {
  const m: Record<string, { type: string; label: string }[]> = {};
  for (const n of props.registry?.nodes ?? []) {
    (m[n.category] ??= []).push({ type: n.type, label: n.label });
  }
  return m;
});

const groupOrder: { id: string; label: string }[] = [
  { id: "trigger",   label: "触发" },
  { id: "action",    label: "动作" },
  { id: "condition", label: "条件" },
];

function onDragStart(e: DragEvent, type: string) {
  if (!e.dataTransfer) return;
  e.dataTransfer.setData("application/vnd.lark-node-type", type);
  e.dataTransfer.effectAllowed = "move";
}
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- 折叠 / 展开按钮 -->
    <button
      class="h-9 w-full flex items-center justify-center gap-1.5
             text-caption text-ink-500 hover:text-ink-900 hover:bg-white/70
             transition duration-200 ease-out-quart border-b border-white/40"
      :title="props.collapsed ? '展开节点面板' : '折叠节点面板'"
      @click="emit('update:collapsed', !props.collapsed)"
    >
      <ChevronsRight v-if="props.collapsed" class="w-4 h-4" />
      <template v-else>
        <ChevronsLeft class="w-4 h-4" />
        <span>节点</span>
      </template>
    </button>

    <!-- ── 折叠态:仅图标列 ── -->
    <div v-if="props.collapsed" class="flex-1 overflow-y-auto py-2 space-y-1 px-1.5">
      <template v-for="group in groupOrder" :key="group.id">
        <div
          v-for="n in grouped[group.id] ?? []"
          :key="n.type"
          :draggable="true"
          :title="n.label"
          class="w-9 h-9 mx-auto rounded-md flex items-center justify-center
                 glass-flat cursor-grab active:cursor-grabbing
                 hover:bg-white/85 transition duration-200 ease-out-quart"
          @dragstart="(e) => onDragStart(e, n.type)"
        >
          <component
            :is="metaOf(n.type).icon"
            class="w-4 h-4"
            :style="{ color: metaOf(n.type).color }"
          />
        </div>
      </template>
    </div>

    <!-- ── 展开态:完整面板 ── -->
    <div v-else class="flex-1 overflow-y-auto px-3 py-3 space-y-4">
      <div v-for="group in groupOrder" :key="group.id">
        <div v-if="grouped[group.id]?.length" class="space-y-1.5">
          <div class="text-[11px] uppercase tracking-wide text-ink-500 px-1 mb-1">
            {{ group.label }}
          </div>
          <div
            v-for="n in grouped[group.id]"
            :key="n.type"
            :draggable="true"
            class="glass-flat rounded-md px-3 py-2 flex items-center gap-2.5
                   cursor-grab active:cursor-grabbing
                   hover:bg-white/85 transition duration-200 ease-out-quart"
            @dragstart="(e) => onDragStart(e, n.type)"
          >
            <component
              :is="metaOf(n.type).icon"
              class="w-4 h-4"
              :style="{ color: metaOf(n.type).color }"
            />
            <span class="text-body text-ink-900">{{ n.label }}</span>
          </div>
        </div>
      </div>

      <p class="text-caption text-ink-400 px-1 leading-relaxed">
        把节点拖到画布上;在节点上拽小圆点连线。
      </p>
    </div>
  </div>
</template>
