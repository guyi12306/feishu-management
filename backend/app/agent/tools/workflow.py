"""工作流草稿相关工具(Agent 用来落 / 改草稿)。"""
from __future__ import annotations

from ...db import dump_json, get_conn, parse_json
from ...workflow_events import localize_graph_events
from .base import ToolContext, ToolError, register


_GRAPH_SCHEMA = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "description": "节点列表;每个 {id, type, position:{x,y}, config:{...}}",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "position": {
                        "type": "object",
                        "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                        "required": ["x", "y"],
                    },
                    "config": {"type": "object"},
                },
                "required": ["id", "type", "config"],
            },
        },
        "edges": {
            "type": "array",
            "description": "连线;每条 {id, source, target}",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                },
                "required": ["id", "source", "target"],
            },
        },
    },
    "required": ["nodes", "edges"],
}


@register(
    "create_draft",
    "在草稿箱里创建一份工作流草稿。"
    "调用后,前端会以卡片形式在对话里展示这条草稿,用户可以点【进草稿箱编辑】或【应用】。"
    "你 **不能**直接执行/应用,只能产出草稿。",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "短标题(≤24 字)"},
            "description": {"type": "string", "description": "1-2 句话的中文说明"},
            "graph": _GRAPH_SCHEMA,
        },
        "required": ["name", "description", "graph"],
    },
)
async def create_draft(
    ctx: ToolContext, name: str, description: str, graph: dict
) -> dict:
    if not graph.get("nodes"):
        raise ToolError("草稿至少要有一个 trigger 节点")
    if not any(str(n.get("type", "")).startswith("trigger.") for n in graph["nodes"]):
        raise ToolError("缺少 trigger.* 触发节点")

    graph.setdefault("viewport", {"x": 0, "y": 0, "zoom": 1})
    graph = localize_graph_events(graph)

    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO workflow_drafts "
        "(user_id, name, description, graph, source_conversation_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (ctx.user_id, name.strip()[:64], description, dump_json(graph), ctx.conversation_id),
    )
    draft_id = cur.lastrowid
    return {
        "draft_id": draft_id,
        "name": name,
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph.get("edges", [])),
    }


@register(
    "update_draft",
    "更新一份已有草稿(用户提了'改一下'之类的请求时)。传 draft_id + 想覆盖的字段。",
    {
        "type": "object",
        "properties": {
            "draft_id": {"type": "integer"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "graph": _GRAPH_SCHEMA,
        },
        "required": ["draft_id"],
    },
)
async def update_draft(
    ctx: ToolContext,
    draft_id: int,
    name: str | None = None,
    description: str | None = None,
    graph: dict | None = None,
) -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (draft_id, ctx.user_id),
    ).fetchone()
    if row is None:
        raise ToolError(f"草稿 {draft_id} 不存在")

    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name.strip()[:64])
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if graph is not None:
        graph.setdefault("viewport", {"x": 0, "y": 0, "zoom": 1})
        graph = localize_graph_events(graph)
        fields.append("graph = ?")
        values.append(dump_json(graph))
    if not fields:
        return {"draft_id": draft_id, "changed": False}

    fields.append("updated_at = datetime('now')")
    values.append(draft_id)
    conn.execute(
        f"UPDATE workflow_drafts SET {', '.join(fields)} WHERE id = ?",
        values,
    )
    return {"draft_id": draft_id, "changed": True}


@register(
    "list_drafts",
    "列出当前用户的工作流草稿(便于'看看现有的工作流')。",
    {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["draft", "applied", "archived"],
                "description": "可选,按状态过滤",
            }
        },
    },
)
async def list_drafts(ctx: ToolContext, status: str | None = None) -> list[dict]:
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT id, name, description, status, updated_at "
            "FROM workflow_drafts WHERE user_id = ? AND status = ? "
            "ORDER BY updated_at DESC LIMIT 50",
            (ctx.user_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, description, status, updated_at "
            "FROM workflow_drafts WHERE user_id = ? "
            "ORDER BY updated_at DESC LIMIT 50",
            (ctx.user_id,),
        ).fetchall()
    return [dict(r) for r in rows]
