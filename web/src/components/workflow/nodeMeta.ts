import {
  CalendarClock,
  Database,
  Send,
  Globe,
  GitBranch,
  Workflow,
  AtSign,
  PencilLine,
} from "lucide-vue-next";

export type NodeCategory = "trigger" | "action" | "condition";

export interface NodeMeta {
  category: NodeCategory;
  label: string;
  icon: any;
  color: string;       // 主色,用于左边竖条
  hue: string;         // 浅色填充
}

const ICON: Record<string, any> = {
  "trigger.schedule":       CalendarClock,
  "trigger.bitable_change": Database,
  "trigger.bot_mention":    AtSign,
  "action.bitable_query":   Database,
  "action.bitable_update":  PencilLine,
  "action.send_message":    Send,
  "action.http":            Globe,
  "condition.if":           GitBranch,
};

const LABEL: Record<string, string> = {
  "trigger.schedule":       "定时触发",
  "trigger.bitable_change": "表格变更",
  "trigger.bot_mention":    "@机器人触发",
  "action.bitable_query":   "查询表格",
  "action.bitable_update":  "修改表格（多维表格）",
  "action.send_message":    "发送消息",
  "action.http":            "HTTP 请求",
  "condition.if":           "条件分支",
};

export function categoryOf(type: string): NodeCategory {
  if (type.startsWith("trigger.")) return "trigger";
  if (type.startsWith("condition.")) return "condition";
  return "action";
}

export function metaOf(type: string): NodeMeta {
  const cat = categoryOf(type);
  const color = cat === "trigger" ? "#4F46E5"
              : cat === "condition" ? "#D4A056"
              : "#0F1419";
  const hue = cat === "trigger" ? "rgba(79,70,229,0.08)"
            : cat === "condition" ? "rgba(212,160,86,0.10)"
            : "rgba(15,20,25,0.06)";
  return {
    category: cat,
    label: LABEL[type] ?? type,
    icon: ICON[type] ?? Workflow,
    color,
    hue,
  };
}
