<script setup lang="ts">
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from "lucide-vue-next";

import { useToastStore } from "@/stores/toast";

const toast = useToastStore();

const ICON = {
  ok: CheckCircle2,
  err: AlertCircle,
  info: Info,
  warn: AlertTriangle,
} as const;

const COLOR = {
  ok: "text-success",
  err: "text-danger",
  info: "text-brand-500",
  warn: "text-gold-500",
} as const;
</script>

<template>
  <div class="fixed top-5 right-5 z-50 flex flex-col gap-2 max-w-md pointer-events-none">
    <TransitionGroup
      enter-active-class="transition duration-300 ease-out-quart"
      enter-from-class="translate-x-10 opacity-0"
      enter-to-class="translate-x-0 opacity-100"
      leave-active-class="transition duration-200 ease-out-quart"
      leave-from-class="translate-x-0 opacity-100"
      leave-to-class="translate-x-10 opacity-0"
    >
      <div
        v-for="t in toast.items"
        :key="t.id"
        class="glass-strong rounded-lg px-3.5 py-2.5 flex items-start gap-2.5
               text-body shadow-glass-strong pointer-events-auto"
      >
        <component :is="ICON[t.kind]"
                   class="w-4 h-4 mt-0.5 shrink-0"
                   :class="COLOR[t.kind]" />
        <div class="flex-1 text-ink-900 break-words">{{ t.message }}</div>
        <button
          class="text-ink-400 hover:text-ink-700 w-5 h-5 flex items-center justify-center shrink-0"
          @click="toast.dismiss(t.id)"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
