<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Trash2, X } from "lucide-vue-next";

import { bitablesApi, type Bitable, type BitableTable } from "@/api/bitables";
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

interface GraphNode {
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
  botId?: string | null;
  graphNodes?: GraphNode[];
}
const props = defineProps<Props>();
const emit = defineEmits<{
  (e: "update", id: string, config: Record<string, any>): void;
  (e: "remove", id: string): void;
  (e: "close"): void;
}>();

const exampleTemplate = "{{nodes.a1.count}}";
const bitables = ref<Bitable[]>([]);
const tables = ref<BitableTable[]>([]);
const loadingBitables = ref(false);
const loadingTables = ref(false);
const bitableError = ref("");

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

const effectiveBotId = computed(() => {
  const nodeBotId = String(props.node?.config?.bot_id ?? "").trim();
  return nodeBotId || props.botId || undefined;
});

const selectedAppToken = computed(() => String(props.node?.config?.app_token ?? ""));

const recordIdSuggestions = computed(() => {
  return (props.graphNodes ?? [])
    .filter((node) => node.id !== props.node?.id)
    .flatMap((node) => {
      if (node.nodeType === "trigger.bitable_change") {
        return [{
          label: `${metaOf(node.nodeType).label} ${node.id} 的记录`,
          value: `{{nodes.${node.id}.first_action.record_id}}`,
        }];
      }
      if (node.nodeType === "action.bitable_query") {
        return [{
          label: `${metaOf(node.nodeType).label} ${node.id} 的第一条记录`,
          value: `{{nodes.${node.id}.records.0.record_id}}`,
        }];
      }
      return [];
    });
});

async function loadBitables() {
  if (!props.open || !props.node) return;
  const hasBitableField = Object.values(fields.value).some((field) => field.type === "bitable");
  if (!hasBitableField) return;
  loadingBitables.value = true;
  bitableError.value = "";
  try {
    bitables.value = await bitablesApi.list(effectiveBotId.value);
  } catch (e: any) {
    bitables.value = [];
    bitableError.value = e?.response?.data?.detail ?? e?.message ?? "多维表格加载失败";
  } finally {
    loadingBitables.value = false;
  }
}

async function loadTables() {
  if (!props.open || !props.node || !selectedAppToken.value) {
    tables.value = [];
    return;
  }
  const hasTableField = Object.values(fields.value).some((field) => field.type === "bitable_table");
  if (!hasTableField) return;
  loadingTables.value = true;
  bitableError.value = "";
  try {
    tables.value = await bitablesApi.tables(selectedAppToken.value, effectiveBotId.value);
  } catch (e: any) {
    tables.value = [];
    bitableError.value = e?.response?.data?.detail ?? e?.message ?? "数据表加载失败";
  } finally {
    loadingTables.value = false;
  }
}

watch(
  () => [props.open, props.node?.id, effectiveBotId.value],
  () => {
    loadBitables();
  },
  { immediate: true }
);

watch(
  () => [props.open, props.node?.id, selectedAppToken.value, effectiveBotId.value],
  () => {
    loadTables();
  },
  { immediate: true }
);

function setVal(key: string, val: any) {
  if (!props.node) return;
  emit("update", props.node.id, { ...props.node.config, [key]: val });
}

function setBitableToken(val: string) {
  if (!props.node) return;
  emit("update", props.node.id, {
    ...props.node.config,
    app_token: val,
    table_id: "",
  });
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

              <select
                v-else-if="field.type === 'bitable'"
                class="input"
                :disabled="loadingBitables"
                :value="props.node.config[key] ?? ''"
                @change="(e) => setBitableToken((e.target as HTMLSelectElement).value)"
              >
                <option value="">{{ loadingBitables ? "加载中..." : "请选择多维表格" }}</option>
                <option
                  v-for="bitable in bitables"
                  :key="bitable.app_token"
                  :value="bitable.app_token"
                >
                  {{ bitable.name || bitable.app_token }}
                </option>
              </select>

              <select
                v-else-if="field.type === 'bitable_table'"
                class="input"
                :disabled="!props.node.config.app_token || loadingTables"
                :value="props.node.config[key] ?? ''"
                @change="(e) => setVal(key, (e.target as HTMLSelectElement).value)"
              >
                <option value="">
                  {{ !props.node.config.app_token ? "请先选择多维表格" : loadingTables ? "加载中..." : "请选择数据表" }}
                </option>
                <option
                  v-for="table in tables"
                  :key="table.table_id"
                  :value="table.table_id"
                >
                  {{ table.name || table.table_id }}
                </option>
              </select>

              <input
                v-else
                class="input"
                :value="props.node.config[key] ?? field.default ?? ''"
                :placeholder="field.default ?? ''"
                @input="(e) => setVal(key, (e.target as HTMLInputElement).value)"
              />

              <select
                v-if="key === 'record_id' && recordIdSuggestions.length"
                class="input mt-2"
                @change="(e) => {
                  const value = (e.target as HTMLSelectElement).value;
                  if (value) setVal(key, value);
                }"
              >
                <option value="">从前面节点选择记录 ID</option>
                <option
                  v-for="item in recordIdSuggestions"
                  :key="item.value"
                  :value="item.value"
                >
                  {{ item.label }}
                </option>
              </select>

              <span v-if="field.description" class="text-caption text-ink-400 mt-1 block">
                {{ field.description }}
              </span>
            </label>
          </div>

          <div v-if="bitableError" class="text-caption text-danger mt-3">
            {{ bitableError }}
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
