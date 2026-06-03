import client from "./client";

export interface LlmSettings {
  base_url: string;
  model: string;
  has_api_key: boolean;
  api_key_masked: string;
}

export interface FeishuSettings {
  app_id: string;
  has_app_secret: boolean;
  app_secret_masked: string;
  has_verification_token: boolean;
  verification_token_masked: string;
}

export interface FeishuBot {
  id: string;
  name: string;
  app_id: string;
  has_app_secret: boolean;
  app_secret_masked: string;
  has_verification_token: boolean;
  verification_token_masked: string;
  is_default: boolean;
}

export interface FeishuBotPayload {
  name: string;
  app_id: string;
  app_secret?: string;
  verification_token?: string;
  is_default?: boolean;
}

export const settingsApi = {
  async getLlm(): Promise<LlmSettings> {
    const { data } = await client.get("/settings/llm");
    return data;
  },
  async updateLlm(payload: {
    base_url?: string;
    model?: string;
    api_key?: string;
  }): Promise<LlmSettings> {
    const { data } = await client.post("/settings/llm", payload);
    return data;
  },
  async testLlm(): Promise<{ ok: boolean; sample: string }> {
    const { data } = await client.post("/settings/llm/test");
    return data;
  },

  async getFeishu(): Promise<FeishuSettings> {
    const { data } = await client.get("/settings/feishu");
    return data;
  },
  async updateFeishu(payload: {
    app_id?: string;
    app_secret?: string;
    verification_token?: string;
  }): Promise<FeishuSettings> {
    const { data } = await client.post("/settings/feishu", payload);
    return data;
  },
  async testFeishu(): Promise<{ ok: boolean; token_prefix: string }> {
    const { data } = await client.post("/settings/feishu/test");
    return data;
  },
  async listFeishuBots(): Promise<FeishuBot[]> {
    const { data } = await client.get("/settings/feishu/bots");
    return data;
  },
  async createFeishuBot(payload: FeishuBotPayload): Promise<FeishuBot> {
    const { data } = await client.post("/settings/feishu/bots", payload);
    return data;
  },
  async updateFeishuBot(id: string, payload: FeishuBotPayload): Promise<FeishuBot> {
    const { data } = await client.put(`/settings/feishu/bots/${id}`, payload);
    return data;
  },
  async deleteFeishuBot(id: string): Promise<void> {
    await client.delete(`/settings/feishu/bots/${id}`);
  },
  async testFeishuBot(id: string): Promise<{ ok: boolean; token_prefix: string }> {
    const { data } = await client.post(`/settings/feishu/bots/${id}/test`);
    return data;
  },
};
