<script setup lang="ts">
import { computed } from "vue";
import { Trash2, X } from "lucide-vue-next";

import type { FeishuBot } from "@/api/settings";
import type { NodeTypeRegistry } from "@/api/workflows";
import { metaOf } from "./nodeMeta";

interface FieldSchema {
  type: string;
  label?: string;
  required?: boolean;
  default?: any;
  options?: string[];
  description?: string;
}

interface SelectedNode {
  id: string;
  nodeType: string;
  config: Record<string, any>;
}

interface Props {
  registry: NodeTypeRegistry | null;
  node: SelectedNode | null;
  /** 抽屉是否打开;通常 node !== null 时打开 */
  open: boolean;
  bots?: FeishuBot[];
}
const props = defineProps<Props>();
const emit = defineEmits<{
  (e: "update", id: string, config: Record<string, any>): void;
  (e: "remove", id: string): void;
  (e: "close"): void;
}>();

const exampleTemplate = "{{nodes.a1.count}}";

const fields = computed<Record<string, FieldSchema>>(() => {
  if (!props.node || !props.registry) return {};
  const spec = props.registry.nodes.find((n) => n.type === props.node!.nodeType);
  return (spec?.schema ?? {}) as unknown as Record<string, FieldSchema>;
});

const botOptions = computed(() => {
  const options = (props.bots ?? []).map((bot) => ({
    value: bot.id,
    label: bot.is_default ? `${bot.name}（默认）` : bot.name,
  }));
  if (!options.some((item) => item.value === "default")) {
    options.unshift({ value: "default", label: "默认机器人" });
  }
  return options;
});

function setVal(key: string, val: any) {
  if (!props.node) return;
  emit("update", props.node.id, { ...props.node.config, [key]: val });
}
</script>

<template>
  <div
    v-show="props.open"
    class="fixed top-0 right-0 h-full w-[340px] z-30 glass-strong border-l border-white/60
           shadow-glass-strong flex flex-col"
  >
      <!-- Header -->
      <div class="h-14 px-4 flex items-center gap-2 shrink-0 border-b border-white/40">
        <template v-if="props.node">
          <component
            :is="metaOf(props.node.nodeType).icon"
            class="w-4 h-4"
            :style="{ color: metaOf(props.node.nodeType).color }"
          />
          <div class="flex-1 min-w-0">
            <div class="text-[11px] uppercase tracking-wide leading-none"
                 :style="{ color: metaOf(props.node.nodeType).color }">
              {{ metaOf(props.node.nodeType).category === "trigger" ? "触发"
                 : metaOf(props.node.nodeType).category === "condition" ? "条件" : "动作" }}
            </div>
            <div class="text-title text-ink-900 truncate mt-0.5 leading-tight">
              {{ metaOf(props.node.nodeType).label }}
            </div>
          </div>
        </template>
        <div v-else class="flex-1 text-title text-ink-700">节点配置</div>
        <button
          class="text-ink-500 hover:text-ink-900 w-7 h-7 flex items-center justify-center"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto px-4 py-4">
        <div v-if="!props.node" class="text-caption text-ink-400 leading-relaxed">
          在画布上选中一个节点,这里会出现它的配置表单。
          <br/><br/>
          字段值里可以用模板变量,例如
          <code class="bg-white/60 rounded px-1.5 py-0.5">{{ exampleTemplate }}</code>。
        </div>

        <template v-else>
          <div class="text-caption mb-4">ID: {{ props.node.id }}</div>

          <div class="space-y-3.5">
            <label v-for="(field, key) in fields" :key="key" class="block">
              <span class="text-caption text-ink-700 mb-1.5 block">
                {{ field.label ?? key }}
                <span v-if="field.required" class="text-danger">*</span>
              </span>

              <select
                v-if="field.type === 'enum'"
                class="input"
                :value="props.node.config[key] ?? field.default ?? ''"
                @change="(e) => setVal(key, (e.target as HTMLSelectElement).value)"
              >
                <option v-for="opt in field.options ?? []" :key="opt" :value="opt">
                  {{ opt }}
                </option>
              </select>

              <select
                v-else-if="field.type === 'bot'"
                class="input"
                :value="props.node.config[key] ?? field.default ?? 'default'"
                @change="(e) => setVal(key, (e.target as HTMLSelectElement).value)"
              >
                <option v-for="bot in botOptions" :key="bot.value" :value="bot.value">
                  {{ bot.label }}
                </option>
              </select>

              <textarea
                v-else-if="field.type === 'text'"
                class="textarea"
                rows="3"
                :value="props.node.config[key] ?? ''"
                @input="(e) => setVal(key, (e.target as HTMLTextAreaElement).value)"
              />

              <input
                v-else
                class="input"
                :value="props.node.config[key] ?? field.default ?? ''"
                :placeholder="field.default ?? ''"
                @input="(e) => setVal(key, (e.target as HTMLInputElement).value)"
              />

              <span v-if="field.description" class="text-caption text-ink-400 mt-1 block">
                {{ field.description }}
              </span>
            </label>
          </div>

          <button
            class="btn-secondary mt-6 w-full !text-danger hover:!bg-red-50"
            @click="emit('remove', props.node.id)"
          >
            <Trash2 class="w-3.5 h-3.5" />
            删除节点
          </button>
        </template>
      </div>
  </div>
</template>
