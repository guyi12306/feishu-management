import client from "./client";

export interface Bitable {
  app_token: string;
  name: string;
  url?: string;
  owner_id?: string;
}

export interface BitableTable {
  table_id: string;
  name: string;
  revision?: number;
}

export interface BitableField {
  field_id: string;
  name: string;
  type?: number;
  ui_type?: string;
  property?: Record<string, unknown>;
}

export const bitablesApi = {
  async list(botId?: string | null): Promise<Bitable[]> {
    const { data } = await client.get("/bitables", {
      params: botId ? { bot_id: botId } : {},
    });
    return data;
  },

  async tables(appToken: string, botId?: string | null): Promise<BitableTable[]> {
    const { data } = await client.get(`/bitables/${appToken}/tables`, {
      params: botId ? { bot_id: botId } : {},
    });
    return data;
  },

  async fields(appToken: string, tableId: string, botId?: string | null): Promise<BitableField[]> {
    const { data } = await client.get(`/bitables/${appToken}/tables/${tableId}/fields`, {
      params: botId ? { bot_id: botId } : {},
    });
    return data;
  },
};
