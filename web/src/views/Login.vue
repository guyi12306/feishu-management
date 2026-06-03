<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Sparkles } from "lucide-vue-next";

import GlassPanel from "@/components/ui/GlassPanel.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import { useAuthStore } from "@/stores/auth";

const username = ref("admin");
const password = ref("");
const loading = ref(false);
const error = ref("");

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

async function onSubmit() {
  if (!username.value || !password.value) {
    error.value = "请输入用户名和密码";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    await auth.login(username.value, password.value);
    const from = (route.query.from as string) || "/chat";
    router.replace(from);
  } catch (e: any) {
    error.value = e?.response?.data?.detail || "登录失败,请重试";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-12">
    <GlassPanel variant="strong" padding="p-10" rounded="rounded-xl"
                class="w-full max-w-md animate-rise">
      <div class="flex items-center gap-3 mb-1">
        <div class="w-10 h-10 rounded-lg bg-brand-500 flex items-center justify-center
                    shadow-[0_8px_24px_rgba(79,70,229,0.35)]">
          <Sparkles class="w-5 h-5 text-white" />
        </div>
        <div>
          <div class="text-title text-ink-900">飞书自动化智能体</div>
          <div class="text-caption">用一句话,搭一条工作流</div>
        </div>
      </div>

      <form class="mt-8 space-y-4" @submit.prevent="onSubmit">
        <Input
          v-model="username"
          label="用户名"
          autocomplete="username"
          placeholder="admin"
        />
        <Input
          v-model="password"
          type="password"
          label="密码"
          autocomplete="current-password"
          placeholder="••••••••"
          :error="error"
        />

        <Button type="submit" class="w-full mt-2" :loading="loading">
          登录
        </Button>

        <p class="text-caption text-ink-400 text-center mt-3">
          初始账号:admin / admin123 · 登录后请改密
        </p>
      </form>
    </GlassPanel>
  </div>
</template>
