import client from "./client";

export type WorkflowStatus = "draft" | "applied" | "archived";

export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  config: Record<string, unknown>;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  viewport: { x: number; y: number; zoom: number };
}

export interface WorkflowSummary {
  id: number;
  name: string;
  description: string | null;
  status: WorkflowStatus;
  bot_id: string | null;
  source_conversation_id: number | null;
  updated_at: string;
  last_applied_at: string | null;
}

export interface WorkflowDetail extends WorkflowSummary {
  graph: WorkflowGraph;
  applied_target: Record<string, unknown> | null;
}

export interface NodeTypeSpec {
  type: string;
  category: string;
  label: string;
  schema: Record<string, Record<string, unknown>>;
}

export interface NodeTypeRegistry {
  categories: { id: string; label: string; color: string }[];
  nodes: NodeTypeSpec[];
}

export const workflowsApi = {
  async list(status?: WorkflowStatus): Promise<WorkflowSummary[]> {
    const { data } = await client.get("/workflows", {
      params: status ? { status_filter: status } : {},
    });
    return data;
  },
  async get(id: number): Promise<WorkflowDetail> {
    const { data } = await client.get(`/workflows/${id}`);
    return data;
  },
  async create(payload?: {
    name?: string;
    description?: string;
    graph?: WorkflowGraph;
    bot_id?: string | null;
  }): Promise<WorkflowDetail> {
    const { data } = await client.post("/workflows", payload ?? {});
    return data;
  },
  async update(
    id: number,
    payload: {
      name?: string;
      description?: string;
      graph?: WorkflowGraph;
      status?: WorkflowStatus;
      bot_id?: string | null;
    }
  ): Promise<WorkflowDetail> {
    const { data } = await client.put(`/workflows/${id}`, payload);
    return data;
  },
  async remove(id: number): Promise<void> {
    await client.delete(`/workflows/${id}`);
  },
  async duplicate(id: number): Promise<WorkflowDetail> {
    const { data } = await client.post(`/workflows/${id}/duplicate`);
    return data;
  },
  async fromMessage(message_id: number): Promise<WorkflowDetail> {
    const { data } = await client.post("/workflows/from-message", { message_id });
    return data;
  },
  async nodeTypes(): Promise<NodeTypeRegistry> {
    const { data } = await client.get("/workflows/node-types");
    return data;
  },

  async apply(id: number): Promise<{ ok: boolean; next_run: string | null; cron: string }> {
    const { data } = await client.post(`/workflows/${id}/apply`);
    return data;
  },

  async unapply(id: number): Promise<void> {
    await client.post(`/workflows/${id}/unapply`);
  },

  async runNow(id: number): Promise<any> {
    const { data } = await client.post(`/workflows/${id}/run-now`);
    return data;
  },
};
