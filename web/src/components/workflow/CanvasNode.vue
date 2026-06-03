<script setup lang="ts">
import { computed } from "vue";
import { Handle, Position } from "@vue-flow/core";

import { metaOf } from "./nodeMeta";

interface Props {
  id: string;
  type: string;
  data: {
    nodeType: string;
    config: Record<string, any>;
    selected?: boolean;
  };
  selected?: boolean;
}
const props = defineProps<Props>();

const meta = computed(() => metaOf(props.data.nodeType));
const isTrigger = computed(() => meta.value.category === "trigger");
const isCondition = computed(() => meta.value.category === "condition");

const preview = computed(() => {
  const c = props.data.config ?? {};
  switch (props.data.nodeType) {
    case "trigger.schedule":       return c.cron ?? "—";
    case "trigger.bitable_change": return `${c.table_id ?? "—"} · ${c.event ?? "—"}`;
    case "trigger.bot_mention":    return c.keyword ? `关键词: ${c.keyword}` : (c.chat_type ?? "全部");
    case "action.bitable_query":   return c.table_id ?? "—";
    case "action.send_message":    return c.chat_id ?? "—";
    case "action.http":            return `${(c.method ?? "GET").toUpperCase()} ${c.url ?? "—"}`;
    case "condition.if":           return c.expression ?? "—";
    default: return "";
  }
});
</script>

<template>
  <div
    class="rounded-lg w-[220px] glass-strong transition duration-200 ease-out-quart relative
           overflow-hidden"
    :class="props.selected
      ? 'ring-2 ring-brand-400 shadow-[0_16px_40px_rgba(79,70,229,0.30)]'
      : 'shadow-glass'"
  >
    <!-- 左侧主色竖条 -->
    <div class="absolute left-0 top-0 bottom-0 w-1" :style="{ background: meta.color }" />

    <Handle
      v-if="!isTrigger"
      type="target"
      :position="Position.Left"
      class="!w-2.5 !h-2.5 !border-2 !border-white !bg-ink-400"
    />
    <Handle
      type="source"
      :position="Position.Right"
      class="!w-2.5 !h-2.5 !border-2 !border-white"
      :style="{ background: meta.color }"
    />

    <div class="px-3 py-2.5 pl-4">
      <div class="flex items-center gap-2 mb-1">
        <component :is="meta.icon" class="w-3.5 h-3.5" :style="{ color: meta.color }" />
        <span class="text-[11px] uppercase tracking-wide font-medium"
              :style="{ color: meta.color }">
          {{ isTrigger ? "触发" : isCondition ? "条件" : "动作" }}
        </span>
      </div>
      <div class="text-body text-ink-900 font-medium">{{ meta.label }}</div>
      <div class="text-caption truncate">{{ preview }}</div>
    </div>
  </div>
</template>
