import { defineStore } from "pinia";
import { ref } from "vue";

import {
  workflowsApi,
  type NodeTypeRegistry,
  type WorkflowDetail,
  type WorkflowStatus,
  type WorkflowSummary,
} from "@/api/workflows";

export const useWorkflowsStore = defineStore("workflows", () => {
  const list = ref<WorkflowSummary[]>([]);
  const current = ref<WorkflowDetail | null>(null);
  const nodeTypes = ref<NodeTypeRegistry | null>(null);
  const loading = ref(false);

  async function loadList(status?: WorkflowStatus) {
    loading.value = true;
    try {
      list.value = await workflowsApi.list(status);
    } finally {
      loading.value = false;
    }
  }

  async function open(id: number) {
    current.value = await workflowsApi.get(id);
  }

  async function loadNodeTypes() {
    if (nodeTypes.value) return nodeTypes.value;
    nodeTypes.value = await workflowsApi.nodeTypes();
    return nodeTypes.value;
  }

  async function create(name?: string) {
    const detail = await workflowsApi.create({ name });
    list.value.unshift({
      id: detail.id,
      name: detail.name,
      description: detail.description,
      status: detail.status,
      bot_id: detail.bot_id,
      source_conversation_id: detail.source_conversation_id,
      updated_at: detail.updated_at,
      last_applied_at: detail.last_applied_at,
    });
    return detail;
  }

  async function update(
    id: number,
    payload: Parameters<typeof workflowsApi.update>[1]
  ) {
    const detail = await workflowsApi.update(id, payload);
    if (current.value?.id === id) current.value = detail;
    const item = list.value.find((w) => w.id === id);
    if (item) {
      item.name = detail.name;
      item.description = detail.description;
      item.status = detail.status;
      item.bot_id = detail.bot_id;
      item.updated_at = detail.updated_at;
    }
    return detail;
  }

  async function remove(id: number) {
    await workflowsApi.remove(id);
    list.value = list.value.filter((w) => w.id !== id);
    if (current.value?.id === id) current.value = null;
  }

  return {
    list,
    current,
    nodeTypes,
    loading,
    loadList,
    open,
    loadNodeTypes,
    create,
    update,
    remove,
  };
});
