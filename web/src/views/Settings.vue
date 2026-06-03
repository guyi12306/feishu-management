<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { AlertCircle, CheckCircle2, Copy, Loader2, Plus, Star, Trash2 } from "lucide-vue-next";

import GlassPanel from "@/components/ui/GlassPanel.vue";
import { authApi } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
import { settingsApi, type FeishuBot, type LlmSettings } from "@/api/settings";
import { useToastStore } from "@/stores/toast";

const toast = useToastStore();
const auth = useAuthStore();

const llm = ref<LlmSettings>({
  base_url: "",
  model: "",
  has_api_key: false,
  api_key_masked: "",
});
const llmKey = ref("");
const llmSaving = ref(false);
const llmTesting = ref(false);
const llmStatus = ref<{ kind: "ok" | "err"; msg: string } | null>(null);

const bots = ref<FeishuBot[]>([]);
const editingBotId = ref<string | null>(null);
const botForm = ref({
  name: "",
  app_id: "",
  app_secret: "",
  verification_token: "",
  is_default: false,
});
const botSaving = ref(false);
const botTesting = ref(false);
const botStatus = ref<{ kind: "ok" | "err"; msg: string } | null>(null);

const editingBot = computed(() =>
  editingBotId.value ? bots.value.find((b) => b.id === editingBotId.value) ?? null : null
);

const webhookUrl = computed(() => `${window.location.origin}/api/webhook/lark`);

async function copyWebhook() {
  try {
    await navigator.clipboard.writeText(webhookUrl.value);
    toast.ok("已复制 webhook URL");
  } catch {
    toast.err("复制失败,请手动选中");
  }
}

function resetBotForm() {
  editingBotId.value = null;
  botForm.value = {
    name: "",
    app_id: "",
    app_secret: "",
    verification_token: "",
    is_default: bots.value.length === 0,
  };
  botStatus.value = null;
}

function editBot(bot: FeishuBot) {
  editingBotId.value = bot.id;
  botForm.value = {
    name: bot.name,
    app_id: bot.app_id,
    app_secret: "",
    verification_token: "",
    is_default: bot.is_default,
  };
  botStatus.value = null;
}

async function loadBots() {
  bots.value = await settingsApi.listFeishuBots();
  if (bots.value.length && !editingBotId.value) editBot(bots.value[0]);
  if (!bots.value.length) resetBotForm();
}

onMounted(async () => {
  llm.value = await settingsApi.getLlm();
  await loadBots();
});

async function saveLlm() {
  llmSaving.value = true;
  llmStatus.value = null;
  try {
    llm.value = await settingsApi.updateLlm({
      base_url: llm.value.base_url,
      model: llm.value.model,
      api_key: llmKey.value || undefined,
    });
    llmKey.value = "";
    llmStatus.value = { kind: "ok", msg: "已保存" };
  } catch (e: any) {
    llmStatus.value = { kind: "err", msg: e?.response?.data?.detail ?? "保存失败" };
  } finally {
    llmSaving.value = false;
  }
}

async function testLlm() {
  llmTesting.value = true;
  llmStatus.value = null;
  try {
    const r = await settingsApi.testLlm();
    llmStatus.value = { kind: "ok", msg: `连接 OK · 模型回:${r.sample}` };
  } catch (e: any) {
    llmStatus.value = { kind: "err", msg: e?.response?.data?.detail ?? "测试失败" };
  } finally {
    llmTesting.value = false;
  }
}

async function saveBot() {
  if (!botForm.value.name.trim()) {
    toast.err("机器人名称不能为空");
    return;
  }
  if (!botForm.value.app_id.trim()) {
    toast.err("App ID 不能为空");
    return;
  }
  botSaving.value = true;
  botStatus.value = null;
  const payload = {
    name: botForm.value.name,
    app_id: botForm.value.app_id,
    app_secret: botForm.value.app_secret || undefined,
    verification_token: botForm.value.verification_token || undefined,
    is_default: botForm.value.is_default,
  };
  try {
    const bot = editingBotId.value
      ? await settingsApi.updateFeishuBot(editingBotId.value, payload)
      : await settingsApi.createFeishuBot(payload);
    botStatus.value = { kind: "ok", msg: "已保存" };
    await loadBots();
    editBot(bot);
  } catch (e: any) {
    botStatus.value = { kind: "err", msg: e?.response?.data?.detail ?? "保存失败" };
  } finally {
    botSaving.value = false;
  }
}

async function testBot() {
  if (!editingBotId.value) return;
  botTesting.value = true;
  botStatus.value = null;
  try {
    const r = await settingsApi.testFeishuBot(editingBotId.value);
    botStatus.value = { kind: "ok", msg: `连接 OK · token 前缀:${r.token_prefix}` };
  } catch (e: any) {
    botStatus.value = { kind: "err", msg: e?.response?.data?.detail ?? "测试失败" };
  } finally {
    botTesting.value = false;
  }
}

async function removeBot(bot: FeishuBot) {
  if (!confirm(`删除机器人「${bot.name}」? 已选择它的工作流会回到默认机器人。`)) return;
  await settingsApi.deleteFeishuBot(bot.id);
  toast.ok("已删除");
  editingBotId.value = null;
  await loadBots();
}

const pwd = ref({ old: "", n1: "", n2: "" });
const pwdSaving = ref(false);

async function changePassword() {
  if (!pwd.value.old || !pwd.value.n1 || pwd.value.n1 !== pwd.value.n2) {
    toast.err("两次新密码不一致或为空");
    return;
  }
  if (pwd.value.n1.length < 6) {
    toast.err("新密码至少 6 位");
    return;
  }
  pwdSaving.value = true;
  try {
    await authApi.changePassword(pwd.value.old, pwd.value.n1);
    toast.ok("密码已修改");
    pwd.value = { old: "", n1: "", n2: "" };
  } catch (e: any) {
    toast.err(e?.response?.data?.detail ?? "修改失败");
  } finally {
    pwdSaving.value = false;
  }
}
</script>

<template>
  <div class="flex-1 h-full overflow-y-auto px-8 py-6">
    <div class="max-w-4xl mx-auto space-y-6">
      <div>
        <div class="text-display text-ink-900">设置</div>
        <p class="text-body text-ink-500 mt-1.5">
          凭证只存本地服务端,加密落库(Fernet/PBKDF2),不会外发。
        </p>
      </div>

      <GlassPanel padding="p-6">
        <div class="text-title text-ink-900 mb-1">账号</div>
        <p class="text-caption text-ink-500 mb-4">
          当前登录:{{ auth.user?.display_name ?? auth.user?.username }}
        </p>

        <div class="grid grid-cols-1 gap-3.5">
          <label class="block">
            <span class="text-caption text-ink-700 mb-1.5 block">原密码</span>
            <input v-model="pwd.old" type="password" class="input" autocomplete="current-password" />
          </label>
          <label class="block">
            <span class="text-caption text-ink-700 mb-1.5 block">新密码(≥ 6 位)</span>
            <input v-model="pwd.n1" type="password" class="input" autocomplete="new-password" />
          </label>
          <label class="block">
            <span class="text-caption text-ink-700 mb-1.5 block">再输一次</span>
            <input v-model="pwd.n2" type="password" class="input" autocomplete="new-password" />
          </label>
        </div>

        <div class="flex justify-end mt-4">
          <button class="btn-primary" :disabled="pwdSaving" @click="changePassword">
            <Loader2 v-if="pwdSaving" class="w-3.5 h-3.5 animate-spin" />
            修改密码
          </button>
        </div>
      </GlassPanel>

      <GlassPanel padding="p-6">
        <div class="flex items-start justify-between mb-4">
          <div>
            <div class="text-title text-ink-900">LLM</div>
            <p class="text-caption text-ink-500 mt-1">
              OpenAI 兼容 API。
              <span v-if="llm.has_api_key" class="text-success">已配置 · {{ llm.api_key_masked }}</span>
              <span v-else class="text-ink-400">未配置</span>
            </p>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-3.5">
          <label class="block">
            <span class="text-caption text-ink-700 mb-1.5 block">Base URL</span>
            <input v-model="llm.base_url" class="input" placeholder="https://api.openai.com/v1" />
          </label>
          <label class="block">
            <span class="text-caption text-ink-700 mb-1.5 block">模型</span>
            <input v-model="llm.model" class="input" placeholder="gpt-4o-mini" />
          </label>
          <label class="block">
            <span class="text-caption text-ink-700 mb-1.5 block">
              API Key
              <span class="text-ink-400">· 留空表示不修改</span>
            </span>
            <input
              v-model="llmKey"
              type="password"
              class="input"
              :placeholder="llm.has_api_key ? llm.api_key_masked : 'sk-...'"
            />
          </label>
        </div>

        <div v-if="llmStatus" class="mt-4 flex items-center gap-2 text-caption"
             :class="llmStatus.kind === 'ok' ? 'text-success' : 'text-danger'">
          <CheckCircle2 v-if="llmStatus.kind === 'ok'" class="w-3.5 h-3.5" />
          <AlertCircle v-else class="w-3.5 h-3.5" />
          {{ llmStatus.msg }}
        </div>

        <div class="flex justify-end gap-2 mt-5">
          <button class="btn-secondary" :disabled="llmTesting || !llm.has_api_key" @click="testLlm">
            <Loader2 v-if="llmTesting" class="w-3.5 h-3.5 animate-spin" />
            测试连接
          </button>
          <button class="btn-primary" :disabled="llmSaving" @click="saveLlm">
            <Loader2 v-if="llmSaving" class="w-3.5 h-3.5 animate-spin" />
            保存
          </button>
        </div>
      </GlassPanel>

      <GlassPanel padding="p-6">
        <div class="flex items-start justify-between gap-3 mb-4">
          <div>
            <div class="text-title text-ink-900">飞书机器人</div>
            <p class="text-caption text-ink-500 mt-1">
              每个机器人对应一套 App ID / Secret。工作流可以选择不同机器人执行。
            </p>
          </div>
          <button class="btn-secondary shrink-0" @click="resetBotForm">
            <Plus class="w-3.5 h-3.5" />
            新增机器人
          </button>
        </div>

        <div class="grid grid-cols-[260px_1fr] gap-5">
          <div class="space-y-2">
            <button
              v-for="bot in bots"
              :key="bot.id"
              class="glass-flat w-full rounded-md px-3 py-2.5 text-left hover:bg-white/85"
              :class="editingBotId === bot.id ? 'ring-2 ring-brand-400' : ''"
              @click="editBot(bot)"
            >
              <div class="flex items-center gap-2">
                <div class="text-body text-ink-900 truncate flex-1">{{ bot.name }}</div>
                <Star v-if="bot.is_default" class="w-3.5 h-3.5 text-gold-500 fill-current" />
              </div>
              <div class="text-caption text-ink-500 truncate">
                {{ bot.app_id || "未填写 App ID" }}
              </div>
            </button>
            <div v-if="!bots.length" class="text-caption text-ink-400 px-2 py-4 text-center">
              还没有机器人配置。
            </div>
          </div>

          <div class="min-w-0">
            <div class="grid grid-cols-1 gap-3.5">
              <label class="block">
                <span class="text-caption text-ink-700 mb-1.5 block">机器人名称</span>
                <input v-model="botForm.name" class="input" placeholder="销售机器人" />
              </label>
              <label class="block">
                <span class="text-caption text-ink-700 mb-1.5 block">App ID</span>
                <input v-model="botForm.app_id" class="input" placeholder="cli_xxxxxxxxxxxx" />
              </label>
              <label class="block">
                <span class="text-caption text-ink-700 mb-1.5 block">
                  App Secret
                  <span class="text-ink-400">· 留空表示不修改</span>
                </span>
                <input
                  v-model="botForm.app_secret"
                  type="password"
                  class="input"
                  :placeholder="editingBot?.has_app_secret ? editingBot.app_secret_masked : ''"
                />
              </label>
              <label class="block">
                <span class="text-caption text-ink-700 mb-1.5 block">
                  Verification Token
                  <span class="text-ink-400">· 表格变更触发器需要</span>
                </span>
                <input
                  v-model="botForm.verification_token"
                  type="password"
                  class="input"
                  :placeholder="editingBot?.has_verification_token ? editingBot.verification_token_masked : 'v_xxxxxxxxxxxxxxxx'"
                />
              </label>
              <label class="inline-flex items-center gap-2 text-body text-ink-700">
                <input v-model="botForm.is_default" type="checkbox" class="accent-brand-500" />
                设为默认机器人
              </label>
            </div>

            <div class="mt-4 glass-flat rounded-md px-3 py-2.5 flex items-center gap-2">
              <div class="flex-1 min-w-0">
                <div class="text-caption text-ink-700 mb-0.5">事件订阅 Webhook URL</div>
                <code class="text-[12px] text-ink-900 break-all">{{ webhookUrl }}</code>
              </div>
              <button
                class="text-ink-500 hover:text-brand-500 w-7 h-7 flex items-center justify-center shrink-0"
                title="复制"
                @click="copyWebhook"
              >
                <Copy class="w-3.5 h-3.5" />
              </button>
            </div>
            <p class="text-caption text-ink-400 mt-2 leading-relaxed">
              每个飞书应用都可以使用同一个 Webhook URL。请在对应应用后台订阅
              <code class="bg-white/60 px-1 rounded">drive.file.bitable_record_changed_v1</code>,
              并关闭「加密」选项。
            </p>

            <div v-if="botStatus" class="mt-4 flex items-center gap-2 text-caption"
                 :class="botStatus.kind === 'ok' ? 'text-success' : 'text-danger'">
              <CheckCircle2 v-if="botStatus.kind === 'ok'" class="w-3.5 h-3.5" />
              <AlertCircle v-else class="w-3.5 h-3.5" />
              {{ botStatus.msg }}
            </div>

            <div class="flex justify-end gap-2 mt-5">
              <button
                v-if="editingBotId"
                class="btn-secondary !text-danger"
                @click="editingBot && removeBot(editingBot)"
              >
                <Trash2 class="w-3.5 h-3.5" />
                删除
              </button>
              <button class="btn-secondary" :disabled="botTesting || !editingBotId" @click="testBot">
                <Loader2 v-if="botTesting" class="w-3.5 h-3.5 animate-spin" />
                测试连接
              </button>
              <button class="btn-primary" :disabled="botSaving" @click="saveBot">
                <Loader2 v-if="botSaving" class="w-3.5 h-3.5 animate-spin" />
                保存机器人
              </button>
            </div>
          </div>
        </div>
      </GlassPanel>
    </div>
  </div>
</template>
