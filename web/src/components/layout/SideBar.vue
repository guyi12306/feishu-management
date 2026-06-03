<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import {
  MessageSquareText,
  Workflow,
  Settings,
  LogOut,
  Sparkles,
} from "lucide-vue-next";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const items = [
  { name: "chat",       label: "对话",   icon: MessageSquareText },
  { name: "workflows",  label: "工作流", icon: Workflow },
  { name: "settings",   label: "设置",   icon: Settings },
] as const;

const active = computed(() => {
  const n = route.name?.toString() ?? "";
  if (n.startsWith("workflow")) return "workflows";
  if (n.startsWith("chat")) return "chat";
  return n;
});

async function onLogout() {
  await auth.logout();
  router.replace({ name: "login" });
}
</script>

<template>
  <aside class="w-[72px] shrink-0 h-full flex flex-col items-center py-5 gap-2
                glass rounded-r-xl border-l-0">
    <!-- Logo -->
    <div class="w-10 h-10 rounded-lg bg-brand-500 flex items-center justify-center mb-4
                shadow-[0_8px_24px_rgba(79,70,229,0.32)]">
      <Sparkles class="w-5 h-5 text-white" />
    </div>

    <RouterLink
      v-for="it in items"
      :key="it.name"
      :to="{ name: it.name }"
      class="w-12 h-12 rounded-md flex flex-col items-center justify-center gap-0.5
             transition duration-200 ease-out-quart group"
      :class="[
        active === it.name
          ? 'bg-brand-500 text-white shadow-[0_4px_14px_rgba(79,70,229,0.28)]'
          : 'text-ink-700 hover:bg-white/70',
      ]"
    >
      <component :is="it.icon" class="w-[18px] h-[18px]" />
      <span class="text-[10px] leading-none">{{ it.label }}</span>
    </RouterLink>

    <div class="flex-1" />

    <button
      class="w-12 h-12 rounded-md flex flex-col items-center justify-center gap-0.5
             text-ink-500 hover:bg-white/70 hover:text-danger
             transition duration-200 ease-out-quart"
      :title="auth.user?.display_name ?? auth.user?.username ?? ''"
      @click="onLogout"
    >
      <LogOut class="w-[18px] h-[18px]" />
      <span class="text-[10px] leading-none">退出</span>
    </button>
  </aside>
</template>
