import { defineStore } from "pinia";
import { ref } from "vue";

export type ToastKind = "info" | "ok" | "err" | "warn";

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

let _id = 0;

export const useToastStore = defineStore("toast", () => {
  const items = ref<Toast[]>([]);

  function push(kind: ToastKind, message: string, timeoutMs = 3500): number {
    const id = ++_id;
    items.value.push({ id, kind, message });
    if (timeoutMs > 0) {
      setTimeout(() => dismiss(id), timeoutMs);
    }
    return id;
  }

  function dismiss(id: number) {
    items.value = items.value.filter((t) => t.id !== id);
  }

  function info(msg: string) {
    return push("info", msg);
  }
  function ok(msg: string) {
    return push("ok", msg);
  }
  function err(msg: string) {
    return push("err", msg, 5000);
  }
  function warn(msg: string) {
    return push("warn", msg);
  }

  return { items, push, dismiss, info, ok, err, warn };
});
