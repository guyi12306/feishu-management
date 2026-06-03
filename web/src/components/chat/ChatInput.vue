<script setup lang="ts">
import { nextTick, ref } from "vue";
import { Send } from "lucide-vue-next";

interface Props {
  loading?: boolean;
  placeholder?: string;
}
const props = withDefaults(defineProps<Props>(), {
  loading: false,
  placeholder: "用一句话描述需要的工作流,例:每天 9 点把销售表近 24h 新增的订单汇总到运维群",
});

const emit = defineEmits<{ (e: "submit", v: string): void }>();

const text = ref("");
const taRef = ref<HTMLTextAreaElement | null>(null);

function autoResize() {
  const ta = taRef.value;
  if (!ta) return;
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
}

async function onSubmit() {
  const v = text.value.trim();
  if (!v || props.loading) return;
  text.value = "";
  await nextTick();
  autoResize();
  emit("submit", v);
}

function onKey(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    onSubmit();
  }
}
</script>

<template>
  <div class="glass-strong rounded-xl p-3 mx-6 mb-6 flex items-end gap-3">
    <textarea
      ref="taRef"
      v-model="text"
      :placeholder="props.placeholder"
      class="textarea flex-1 max-h-[200px] min-h-[44px] bg-transparent
             !shadow-none !border-0 focus:!shadow-none"
      rows="1"
      @keydown="onKey"
      @input="autoResize"
    />
    <button
      class="btn-primary !h-11 !w-11 !p-0 shrink-0"
      :disabled="props.loading || !text.trim()"
      @click="onSubmit"
    >
      <Send class="w-4 h-4" />
    </button>
  </div>
</template>
