import client from "./client";

export interface Chat {
  chat_id: string;
  name: string;
  description?: string;
  tenant_key?: string;
}

export const chatsApi = {
  async list(botId?: string | null): Promise<Chat[]> {
    const { data } = await client.get("/chats", {
      params: botId ? { bot_id: botId } : {},
    });
    return data;
  },
};
