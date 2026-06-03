<script setup lang="ts">
import { computed, ref } from "vue";
import {
  ChevronRight,
  Wrench,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-vue-next";

interface Props {
  name: string;
  /** 待执行的参数 JSON 字符串(原样,可能不完整) */
  argsRaw?: string;
  /** 已执行的结果 */
  result?: unknown;
  ok?: boolean;
  pending?: boolean;
}
const props = defineProps<Props>();

const open = ref(false);

const status = computed(() => {
  if (props.pending) return "pending";
  return props.ok ? "ok" : "err";
});

const labelMap: Record<string, string> = {
  list_bitables: "列出多维表格",
  list_tables: "列出数据表",
  get_table_fields: "查询字段",
  list_chats: "列出群聊",
  create_draft: "生成工作流草稿",
  update_draft: "更新工作流草稿",
  list_drafts: "查工作流草稿",
};
const label = computed(() => labelMap[props.name] ?? props.name);

const parsedArgs = computed(() => {
  if (!props.argsRaw) return null;
  try {
    return JSON.parse(props.argsRaw);
  } catch {
    return props.argsRaw;
  }
});
</script>

<template>
  <div class="glass-flat rounded-md text-caption my-1 inline-block max-w-full">
    <button
      class="px-3 py-1.5 flex items-center gap-2 hover:bg-white/85
             transition duration-200 ease-out-quart rounded-md w-full"
      @click="open = !open"
    >
      <Loader2 v-if="status === 'pending'"
               class="w-3.5 h-3.5 text-brand-500 animate-spin shrink-0" />
      <CheckCircle2 v-else-if="status === 'ok'"
                     class="w-3.5 h-3.5 text-success shrink-0" />
      <XCircle v-else class="w-3.5 h-3.5 text-danger shrink-0" />

      <Wrench class="w-3 h-3 text-ink-500 shrink-0" />
      <span class="text-ink-900 font-medium truncate">{{ label }}</span>

      <span v-if="status === 'pending'" class="text-ink-400 truncate ml-1">
        执行中…
      </span>
      <span v-else-if="status === 'err'" class="text-danger truncate ml-1">
        失败
      </span>

      <ChevronRight
        class="w-3.5 h-3.5 ml-auto text-ink-400 transition duration-200 shrink-0"
        :class="open && 'rotate-90'"
      />
    </button>

    <div v-if="open" class="px-3 pb-2 space-y-1.5 border-t border-white/60 pt-1.5">
      <div v-if="parsedArgs !== null">
        <div class="text-[11px] text-ink-500 mb-0.5">参数</div>
        <pre class="text-[11.5px] bg-white/60 rounded p-2 overflow-x-auto max-w-[420px]"
        >{{ typeof parsedArgs === "string" ? parsedArgs : JSON.stringify(parsedArgs, null, 2) }}</pre>
      </div>
      <div v-if="!pending && result !== undefined">
        <div class="text-[11px] text-ink-500 mb-0.5">结果</div>
        <pre class="text-[11.5px] bg-white/60 rounded p-2 overflow-x-auto max-w-[420px]"
        >{{ typeof result === "string" ? result : JSON.stringify(result, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>
