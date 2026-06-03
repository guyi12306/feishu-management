"""工作流草稿箱 CRUD、应用/撤销和执行历史接口。"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import CurrentUser
from ..db import dump_json, get_conn, parse_json
from .. import feishu_bots
from ..workflow_events import EVENT_ALIASES, localize_graph_events


router = APIRouter(prefix="/api/workflows", tags=["workflows"])


WorkflowStatus = Literal["draft", "applied", "archived"]


REQUIRED_CONFIG: dict[str, tuple[str, ...]] = {
    "trigger.schedule": ("cron", "tz"),
    "trigger.bitable_change": ("app_token", "table_id", "event"),
    "action.bitable_query": ("app_token", "table_id"),
    "action.bitable_update": ("app_token", "table_id", "record_id", "fields"),
    "action.send_message": ("chat_id", "template"),
    "action.http": ("method", "url"),
    "condition.if": ("expression",),
}


class GraphIn(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    viewport: dict[str, Any] = Field(
        default_factory=lambda: {"x": 0, "y": 0, "zoom": 1}
    )


class WorkflowSummary(BaseModel):
    id: int
    name: str
    description: str | None
    status: WorkflowStatus
    bot_id: str | None = None
    source_conversation_id: int | None
    updated_at: str
    last_applied_at: str | None


class WorkflowDetail(WorkflowSummary):
    graph: GraphIn
    applied_target: dict | None


class CreateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: GraphIn | None = None
    bot_id: str | None = None


class UpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: GraphIn | None = None
    status: WorkflowStatus | None = None
    bot_id: str | None = None


class FromMessageIn(BaseModel):
    message_id: int


def _summary(row) -> WorkflowSummary:
    return WorkflowSummary(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        status=row["status"],
        bot_id=row["bot_id"],
        source_conversation_id=row["source_conversation_id"],
        updated_at=row["updated_at"],
        last_applied_at=row["last_applied_at"],
    )


def _detail(row) -> WorkflowDetail:
    graph = parse_json(row["graph"], {"nodes": [], "edges": [], "viewport": {}})
    return WorkflowDetail(
        **_summary(row).model_dump(),
        graph=GraphIn(**localize_graph_events(graph)),
        applied_target=parse_json(row["applied_target"]),
    )


def _validate_apply_graph(graph: dict) -> None:
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    node_ids = {n.get("id") for n in nodes}
    triggers = [n for n in nodes if str(n.get("type", "")).startswith("trigger.")]
    if len(triggers) != 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="工作流必须且只能有一个 trigger.* 触发节点",
        )
    for edge in edges:
        if edge.get("source") not in node_ids or edge.get("target") not in node_ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="工作流存在无效连线")
    for node in nodes:
        ntype = node.get("type")
        cfg = node.get("config") or {}
        for key in REQUIRED_CONFIG.get(ntype, ()):
            value = cfg.get(key)
            if value is None or value == "" or value == "<待选>":
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"节点 {node.get('id')}({ntype}) 缺少配置:{key}",
                )
        if ntype == "trigger.bitable_change":
            event = str(cfg.get("event", "")).strip()
            if event not in EVENT_ALIASES and event.lower() not in EVENT_ALIASES:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"节点 {node.get('id')} 的事件必须是:新增、更新、删除",
                )


@router.get("", response_model=list[WorkflowSummary])
def list_workflows(status_filter: WorkflowStatus | None = None, user: dict = CurrentUser):
    conn = get_conn()
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM workflow_drafts WHERE user_id = ? AND status = ? "
            "ORDER BY updated_at DESC",
            (user["id"], status_filter),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM workflow_drafts WHERE user_id = ? "
            "ORDER BY updated_at DESC",
            (user["id"],),
        ).fetchall()
    return [_summary(r) for r in rows]


@router.post("", response_model=WorkflowDetail)
def create_workflow(payload: CreateIn, user: dict = CurrentUser):
    conn = get_conn()
    if payload.bot_id and not feishu_bots.bot_exists(user["id"], payload.bot_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="机器人配置不存在")
    graph = localize_graph_events((payload.graph or GraphIn()).model_dump())
    cur = conn.execute(
        "INSERT INTO workflow_drafts (user_id, name, description, graph, bot_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            user["id"],
            (payload.name or "未命名工作流").strip() or "未命名工作流",
            payload.description,
            dump_json(graph),
            payload.bot_id,
        ),
    )
    row = conn.execute("SELECT * FROM workflow_drafts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _detail(row)


@router.post("/from-message", response_model=WorkflowDetail)
def from_message(payload: FromMessageIn, user: dict = CurrentUser):
    """把对话里 assistant 消息上挂着的草稿,确认收入草稿箱并返回。

    当前的 mock 实现已经在 /api/chat 直接落库了,这里相当于查回。
    Phase 2 接 LLM 后,Agent 不一定每次都立刻落库,会保留这个端点作为显式入口。
    """
    conn = get_conn()
    msg = conn.execute(
        "SELECT m.draft_id "
        "FROM messages m JOIN conversations c ON c.id = m.conversation_id "
        "WHERE m.id = ? AND c.user_id = ?",
        (payload.message_id, user["id"]),
    ).fetchone()
    if msg is None or msg["draft_id"] is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="该消息没有关联草稿")
    row = conn.execute(
        "SELECT * FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (msg["draft_id"], user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="草稿不存在")
    return _detail(row)


@router.get("/node-types")
def node_types():
    """画布初始化用的节点类型注册表。"""
    return {
        "categories": [
            {"id": "trigger", "label": "触发", "color": "#4F46E5"},
            {"id": "action", "label": "动作", "color": "#0F1419"},
            {"id": "condition", "label": "条件", "color": "#D4A056"},
        ],
        "nodes": [
            {
                "type": "trigger.schedule",
                "category": "trigger",
                "label": "定时触发",
                "schema": {
                    "cron": {"type": "string", "label": "Cron 表达式", "required": True},
                    "tz": {"type": "string", "label": "时区", "default": "Asia/Shanghai"},
                },
            },
            {
                "type": "trigger.bitable_change",
                "category": "trigger",
                "label": "表格变更",
                "schema": {
                    "app_token": {"type": "bitable", "label": "多维表格", "required": True},
                    "table_id": {"type": "bitable_table", "label": "数据表", "required": True},
                    "event": {"type": "enum", "label": "事件",
                              "options": ["新增", "更新", "删除"], "default": "新增"},
                },
            },
            {
                "type": "trigger.bot_mention",
                "category": "trigger",
                "label": "@机器人触发",
                "schema": {
                    "bot_id": {
                        "type": "bot",
                        "label": "机器人",
                        "default": "default",
                        "required": True,
                        "description": "只有这个机器人收到 @ 消息时才触发",
                    },
                    "chat_type": {
                        "type": "enum",
                        "label": "会话类型",
                        "options": ["全部", "群聊", "私聊"],
                        "default": "全部",
                    },
                    "keyword": {
                        "type": "string",
                        "label": "关键词",
                        "description": "可选，消息文本包含该关键词才触发",
                    },
                },
            },
            {
                "type": "action.bitable_query",
                "category": "action",
                "label": "查询表格",
                "schema": {
                    "app_token": {"type": "bitable", "label": "多维表格", "required": True},
                    "table_id": {"type": "bitable_table", "label": "数据表", "required": True},
                    "filter": {"type": "string", "label": "过滤表达式"},
                },
            },
            {
                "type": "action.bitable_update",
                "category": "action",
                "label": "修改表格（多维表格）",
                "schema": {
                    "app_token": {"type": "bitable", "label": "多维表格", "required": True},
                    "table_id": {"type": "bitable_table", "label": "数据表", "required": True},
                    "record_id": {
                        "type": "string",
                        "label": "记录 ID",
                        "required": True,
                        "description": "要修改的记录 ID，可使用模板变量",
                    },
                    "fields": {
                        "type": "text",
                        "label": "更新字段 JSON",
                        "required": True,
                        "description": "例如 {\"状态\":\"已处理\",\"备注\":\"{{nodes.t1.text}}\"}",
                    },
                },
            },
            {
                "type": "action.send_message",
                "category": "action",
                "label": "发送消息",
                "schema": {
                    "chat_id": {"type": "string", "label": "目标群/人", "required": True},
                    "template": {"type": "text", "label": "消息模板", "required": True},
                },
            },
            {
                "type": "action.http",
                "category": "action",
                "label": "HTTP 请求",
                "schema": {
                    "method": {"type": "enum", "label": "方法",
                               "options": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
                    "url": {"type": "string", "label": "URL", "required": True},
                    "body": {"type": "text", "label": "请求体"},
                },
            },
            {
                "type": "condition.if",
                "category": "condition",
                "label": "条件分支",
                "schema": {
                    "expression": {"type": "string", "label": "条件表达式", "required": True},
                },
            },
        ],
    }


@router.get("/{wid}", response_model=WorkflowDetail)
def get_workflow(wid: int, user: dict = CurrentUser):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (wid, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="草稿不存在")
    return _detail(row)


@router.put("/{wid}", response_model=WorkflowDetail)
def update_workflow(wid: int, payload: UpdateIn, user: dict = CurrentUser):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (wid, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="草稿不存在")

    fields: list[str] = []
    values: list[Any] = []
    if payload.name is not None:
        fields.append("name = ?")
        values.append(payload.name.strip() or "未命名工作流")
    if payload.description is not None:
        fields.append("description = ?")
        values.append(payload.description)
    if payload.graph is not None:
        fields.append("graph = ?")
        values.append(dump_json(localize_graph_events(payload.graph.model_dump())))
    if payload.status is not None:
        fields.append("status = ?")
        values.append(payload.status)
    if "bot_id" in payload.model_fields_set:
        if payload.bot_id and not feishu_bots.bot_exists(user["id"], payload.bot_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="机器人配置不存在")
        fields.append("bot_id = ?")
        values.append(payload.bot_id)
    if not fields:
        return _detail(row)

    fields.append("updated_at = datetime('now')")
    values.extend([wid, user["id"]])
    conn.execute(
        f"UPDATE workflow_drafts SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
        values,
    )
    row = conn.execute("SELECT * FROM workflow_drafts WHERE id = ?", (wid,)).fetchone()
    return _detail(row)


@router.delete("/{wid}")
def delete_workflow(wid: int, user: dict = CurrentUser):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, status FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (wid, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="草稿不存在")
    from ..engine import scheduler as engine_scheduler

    engine_scheduler.unregister(wid)
    cur = conn.execute(
        "DELETE FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (wid, user["id"]),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="草稿不存在")
    return {"ok": True}


@router.post("/{wid}/duplicate", response_model=WorkflowDetail)
def duplicate_workflow(wid: int, user: dict = CurrentUser):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (wid, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="草稿不存在")
    cur = conn.execute(
        "INSERT INTO workflow_drafts (user_id, name, description, graph, bot_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (user["id"], f"{row['name']} 副本", row["description"], row["graph"], row["bot_id"]),
    )
    new_row = conn.execute("SELECT * FROM workflow_drafts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _detail(new_row)


@router.post("/{wid}/apply")
def apply_workflow(wid: int, user: dict = CurrentUser):
    """挂到调度器(我们自建引擎,不依赖飞书 OpenAPI 的自动化能力)。

    两种触发器并存:
    - trigger.schedule       → 注册到 APScheduler,按 cron 跑
    - trigger.bitable_change → 不挂调度,等飞书 webhook 推事件触发
    """
    from ..engine import scheduler as engine_scheduler

    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (wid, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="草稿不存在")

    graph = parse_json(row["graph"]) or {"nodes": [], "edges": []}
    _validate_apply_graph(graph)
    nodes = graph.get("nodes") or []
    triggers = [n for n in nodes if str(n.get("type", "")).startswith("trigger.")]

    has_schedule = any(n.get("type") == "trigger.schedule" for n in triggers)
    has_bitable = any(n.get("type") == "trigger.bitable_change" for n in triggers)
    has_bot_mention = any(n.get("type") == "trigger.bot_mention" for n in triggers)
    bot_mention_bot_id = next(
        (
            str((n.get("config") or {}).get("bot_id") or "").strip()
            for n in triggers
            if n.get("type") == "trigger.bot_mention"
            and str((n.get("config") or {}).get("bot_id") or "").strip()
        ),
        None,
    )
    effective_bot_id = bot_mention_bot_id or row["bot_id"]
    if effective_bot_id and not feishu_bots.bot_exists(user["id"], effective_bot_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="工作流选择的机器人不存在")

    applied_target: dict = {"engine": "internal"}
    info: dict = {}

    engine_scheduler.unregister(wid)

    if has_schedule:
        try:
            info = engine_scheduler.register(wid, user["id"], graph)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
        applied_target.update(info)

    if has_bitable or has_bot_mention:
        # 提前校验 verification_token 是否配过,给个友好提示但不阻止
        from .. import secrets_store
        if not secrets_store.get(user["id"], "feishu", "verification_token"):
            applied_target["warning"] = (
                "已应用,但 Verification Token 未配置,飞书事件触发器无法工作 → 去『设置』填一下"
            )

    if has_bitable:
        applied_target["bitable_change"] = True

    if has_bot_mention:
        applied_target["bot_mention"] = True

    conn.execute(
        "UPDATE workflow_drafts SET status = 'applied', bot_id = ?, "
        "applied_target = ?, last_applied_at = datetime('now') "
        "WHERE id = ?",
        (effective_bot_id, dump_json(applied_target), wid),
    )
    return {
        "ok": True,
        "next_run": info.get("next_run"),
        "cron": info.get("cron"),
        "warning": applied_target.get("warning"),
    }


@router.post("/{wid}/unapply")
def unapply_workflow(wid: int, user: dict = CurrentUser):
    from ..engine import scheduler as engine_scheduler

    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (wid, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="草稿不存在")

    engine_scheduler.unregister(wid)
    conn.execute(
        "UPDATE workflow_drafts SET status = 'draft', applied_target = NULL "
        "WHERE id = ?",
        (wid,),
    )
    return {"ok": True}


@router.post("/{wid}/run-now")
async def run_now(wid: int, user: dict = CurrentUser):
    """立即触发一次执行,不依赖 cron。"""
    from ..engine.executor import ExecError, run_workflow

    try:
        result = await run_workflow(
            user_id=user["id"],
            workflow_id=wid,
            trigger="manual",
        )
    except ExecError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "status": result.status,
        "duration_ms": result.duration_ms,
        "error": result.error,
        "log": [entry.__dict__ for entry in result.log],
    }


@router.get("/{wid}/runs")
def list_runs(wid: int, limit: int = 30, user: dict = CurrentUser):
    conn = get_conn()
    own = conn.execute(
        "SELECT id FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (wid, user["id"]),
    ).fetchone()
    if own is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="草稿不存在")

    rows = conn.execute(
        "SELECT id, status, trigger, started_at, finished_at, duration_ms, error "
        "FROM workflow_runs WHERE workflow_id = ? ORDER BY id DESC LIMIT ?",
        (wid, max(1, min(limit, 100))),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{wid}/runs/{run_id}")
def get_run(wid: int, run_id: int, user: dict = CurrentUser):
    conn = get_conn()
    row = conn.execute(
        "SELECT r.* FROM workflow_runs r "
        "JOIN workflow_drafts d ON d.id = r.workflow_id "
        "WHERE r.id = ? AND d.id = ? AND d.user_id = ?",
        (run_id, wid, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="运行记录不存在")
    return {
        **dict(row),
        "log": parse_json(row["log"], []),
    }
