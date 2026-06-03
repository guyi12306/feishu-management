"""工作流执行器 —— 拓扑序遍历 graph,把每个节点的输出灌给下游。

简化决策(Phase 3):
- 不支持条件分支的真正"分叉"(condition.if 当成普通过滤节点 → 表达式为真才往下,否则截断子树)。
- 不支持并行执行;按拓扑序串行跑(够用,后期换 asyncio.gather 容易)。
- 模板变量:`{{nodes.a1.count}}` / `{{trigger.now}}`,从 context 字典取。
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from ..db import dump_json, get_conn, parse_json
from ..lark_client import LarkClient, LarkError
from ..workflow_events import localized_event


class ExecError(Exception):
    pass


@dataclass
class RunLogEntry:
    node_id: str
    node_type: str
    status: str  # ok | err | skipped
    output: Any = None
    error: str | None = None
    duration_ms: int = 0


@dataclass
class RunResult:
    status: str  # success | partial | failed
    log: list[RunLogEntry] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0


AUTOMATIC_TRIGGERS = {"schedule", "bitable_change", "bot_mention"}


_TEMPLATE_RE = re.compile(r"\{\{\s*([\w.\-\[\]]+)\s*\}\}")


def _lookup(ctx: dict, path: str) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return ""
        else:
            return ""
        if cur is None:
            return ""
    return cur


def _render(value: Any, ctx: dict) -> Any:
    if isinstance(value, str):
        def repl(m: re.Match) -> str:
            v = _lookup(ctx, m.group(1))
            if isinstance(v, (dict, list)):
                return json.dumps(v, ensure_ascii=False)
            return "" if v is None else str(v)
        return _TEMPLATE_RE.sub(repl, value)
    if isinstance(value, dict):
        return {k: _render(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, ctx) for v in value]
    return value


def _has_trigger(graph: dict, trigger_type: str) -> bool:
    return any(n.get("type") == trigger_type for n in graph.get("nodes", []))


def _ensure_auto_workflow_active(
    conn,
    *,
    user_id: int,
    workflow_id: int,
) -> None:
    row = conn.execute(
        "SELECT status FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (workflow_id, user_id),
    ).fetchone()
    if row is None:
        raise ExecError(f"Workflow {workflow_id} no longer exists")
    if row["status"] != "applied":
        raise ExecError(f"Workflow {workflow_id} is not applied")


def _parse_filter(value: Any) -> dict | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            raise ExecError("查询表格节点 filter 需要是飞书 records/search 的 JSON filter 对象")
        if isinstance(parsed, dict):
            return parsed
    raise ExecError("查询表格节点 filter 需要是 JSON 对象")


def _parse_update_fields(value: Any) -> dict:
    if isinstance(value, dict):
        if not value:
            raise ExecError("修改表格节点 fields 不能为空")
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ExecError("修改表格节点 fields 不能为空")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise ExecError(f"修改表格节点 fields 需要是 JSON 对象: {e.msg}")
        if isinstance(parsed, dict) and parsed:
            return parsed
    raise ExecError("修改表格节点 fields 需要是非空 JSON 对象")


def _parse_message_content(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or raw == "":
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"text": raw}
    return parsed if isinstance(parsed, dict) else {"text": raw}


def _message_trigger_output(payload: dict) -> dict:
    message = payload.get("message") or {}
    content = _parse_message_content(message.get("content"))
    return {
        "message_id": message.get("message_id"),
        "root_id": message.get("root_id"),
        "parent_id": message.get("parent_id"),
        "chat_id": message.get("chat_id"),
        "chat_type": message.get("chat_type"),
        "message_type": message.get("message_type"),
        "text": content.get("text") or content.get("content") or "",
        "content": content,
        "mentions": message.get("mentions") or [],
        "sender": payload.get("sender") or {},
    }


def _topo_order(nodes: list[dict], edges: list[dict]) -> list[str]:
    """简单 Kahn 拓扑。"""
    incoming: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    outgoing: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in incoming and t in incoming:
            incoming[t].add(s)
            outgoing[s].add(t)

    roots = [nid for nid, ins in incoming.items() if not ins]
    order: list[str] = []
    seen = set()
    while roots:
        nid = roots.pop(0)
        if nid in seen:
            continue
        seen.add(nid)
        order.append(nid)
        for nxt in outgoing.get(nid, ()):
            incoming[nxt].discard(nid)
            if not incoming[nxt]:
                roots.append(nxt)
    if len(order) < len(nodes):
        raise ExecError("Graph 有环或孤立子图,无法执行")
    return order


# ────── 单节点执行 ──────
async def _exec_node(
    *,
    user_id: int,
    bot_id: str | None,
    node: dict,
    ctx: dict,
    upstream_outputs: list[Any],
) -> Any:
    ntype: str = node.get("type", "")
    raw_config: dict = node.get("config") or {}
    cfg = _render(raw_config, ctx)

    # 输入:有上游就用第一个上游 output,没有就空
    incoming = upstream_outputs[0] if upstream_outputs else None
    ctx_local = {**ctx, "input": incoming}

    if ntype == "trigger.schedule":
        return {
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "cron": raw_config.get("cron"),
        }

    if ntype == "trigger.bitable_change":
        # webhook 进来时 ctx['trigger']['payload'] 是飞书事件 event 字段
        payload = ctx.get("trigger", {}).get("payload") or {}
        actions = payload.get("action_list") or []
        first = actions[0] if actions else {}
        return {
            "event": localized_event(raw_config.get("event")),
            "app_token": payload.get("file_token") or payload.get("app_token"),
            "table_id": payload.get("table_id"),
            "action_count": len(actions),
            "first_action": first,
            "first_record": first.get("record") or first.get("after_value"),
        }

    if ntype == "trigger.bot_mention":
        payload = ctx.get("trigger", {}).get("payload") or {}
        return _message_trigger_output(payload)

    if ntype == "action.bitable_query":
        app_token = cfg.get("app_token")
        table_id = cfg.get("table_id")
        if not app_token or app_token == "<待选>":
            raise ExecError("查询表格节点未配置 app_token")
        if not table_id or table_id == "<待选>":
            raise ExecError("查询表格节点未配置 table_id")
        filter_expr = _parse_filter(cfg.get("filter"))
        try:
            cli = LarkClient.for_user(user_id, bot_id)
            data = await cli.search_records(
                app_token,
                table_id,
                filter_expr=filter_expr,
            )
        except LarkError as e:
            raise ExecError(str(e))
        items = data.get("items") or []
        return {"records": items, "count": len(items)}

    if ntype == "action.bitable_update":
        app_token = cfg.get("app_token")
        table_id = cfg.get("table_id")
        record_id = str(cfg.get("record_id") or "").strip()
        if not app_token or app_token == "<待选>":
            raise ExecError("修改表格节点未配置 app_token")
        if not table_id or table_id == "<待选>":
            raise ExecError("修改表格节点未配置 table_id")
        if not record_id or record_id == "<待选>":
            raise ExecError("修改表格节点未配置 record_id")
        fields = _parse_update_fields(cfg.get("fields"))
        try:
            cli = LarkClient.for_user(user_id, bot_id)
            data = await cli.update_record(app_token, table_id, record_id, fields)
        except LarkError as e:
            raise ExecError(str(e))
        return {
            "record_id": record_id,
            "fields": fields,
            "record": data.get("record"),
            "raw": data,
        }

    if ntype == "action.send_message":
        try:
            cli = LarkClient.for_user(user_id, bot_id)
            text = cfg.get("template", "")
            chat_id = cfg.get("chat_id", "")
            if not chat_id or chat_id == "<待选>":
                raise ExecError("发送消息节点未配置目标 chat_id")
            r = await cli.send_message(chat_id, text)
            return {"message_id": r.get("message_id"), "sent_text": text}
        except LarkError as e:
            raise ExecError(str(e))

    if ntype == "action.http":
        method = (cfg.get("method") or "GET").upper()
        url = cfg.get("url")
        if not url:
            raise ExecError("HTTP 节点缺少 url")
        body_raw = cfg.get("body")
        json_body = None
        data_body = None
        if body_raw:
            try:
                json_body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
            except json.JSONDecodeError:
                data_body = body_raw
        async with httpx.AsyncClient(timeout=30) as cli:
            r = await cli.request(method, url, json=json_body, data=data_body)
        try:
            parsed = r.json()
        except Exception:
            parsed = r.text[:2000]
        return {"status": r.status_code, "body": parsed}

    if ntype == "condition.if":
        expr = cfg.get("expression") or "true"
        ok = _safe_eval_bool(expr, ctx_local)
        return {"passed": ok}

    raise ExecError(f"未知节点类型:{ntype}")


def _safe_eval_bool(expr: str, ctx: dict) -> bool:
    """非常受限的布尔表达式 —— 只允许 比较 / and/or/not / 数字 / 字符串 / 变量。"""
    import ast

    expr_clean = _TEMPLATE_RE.sub(
        lambda m: json.dumps(_lookup(ctx, m.group(1)), ensure_ascii=False), expr
    )
    expr_clean = re.sub(r"\btrue\b", "True", expr_clean, flags=re.IGNORECASE)
    expr_clean = re.sub(r"\bfalse\b", "False", expr_clean, flags=re.IGNORECASE)
    expr_clean = re.sub(r"\bnull\b", "None", expr_clean, flags=re.IGNORECASE)
    try:
        tree = ast.parse(expr_clean, mode="eval")
    except SyntaxError as e:
        raise ExecError(f"条件表达式语法错误:{e}")

    allowed = (
        ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
        ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.In, ast.NotIn, ast.Constant, ast.Name, ast.Load,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ExecError(f"条件表达式不允许的节点:{type(node).__name__}")

    try:
        return bool(eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, {}))
    except NameError as e:
        raise ExecError(f"条件表达式包含未知变量:{e}") from e


# ────── 主入口 ──────
async def run_workflow(
    *,
    user_id: int,
    workflow_id: int,
    trigger: str,
    trigger_payload: dict | None = None,
) -> RunResult:
    """跑一次工作流,把执行历史写到 workflow_runs 表。"""
    conn = get_conn()
    wf = conn.execute(
        "SELECT id, graph, bot_id, status FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (workflow_id, user_id),
    ).fetchone()
    if wf is None:
        raise ExecError(f"工作流 {workflow_id} 不存在")
    graph = parse_json(wf["graph"]) or {"nodes": [], "edges": []}
    bot_id = wf["bot_id"]
    if trigger in AUTOMATIC_TRIGGERS:
        if wf["status"] != "applied":
            raise ExecError(f"Workflow {workflow_id} is not applied")
        expected_trigger = f"trigger.{trigger}"
        if not _has_trigger(graph, expected_trigger):
            raise ExecError(f"Workflow {workflow_id} no longer has {expected_trigger}")
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    nodes_by_id = {n["id"]: n for n in nodes}

    # 开启运行记录
    cur = conn.execute(
        "INSERT INTO workflow_runs (workflow_id, user_id, status, trigger) "
        "VALUES (?, ?, 'running', ?)",
        (workflow_id, user_id, trigger),
    )
    run_id = cur.lastrowid

    start = time.time()
    ctx: dict[str, Any] = {
        "trigger": {"kind": trigger, "payload": trigger_payload or {}},
        "nodes": {},
        "vars": {},
    }
    log: list[RunLogEntry] = []
    failed = False
    err_text: str | None = None

    # 上游映射(target → [source...])
    parents: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        if e.get("target") in parents and e.get("source") in nodes_by_id:
            parents[e["target"]].append(e["source"])

    # 跳过集合:condition.if 求值为 false 时,其下游全部跳过
    skipped: set[str] = set()

    try:
        order = _topo_order(nodes, edges)
        for nid in order:
            if trigger in AUTOMATIC_TRIGGERS:
                _ensure_auto_workflow_active(
                    conn,
                    user_id=user_id,
                    workflow_id=workflow_id,
                )
            node = nodes_by_id[nid]
            ntype = node.get("type", "")

            # 上游有任何被 skip → 自己也 skip
            if any(p in skipped for p in parents[nid]):
                skipped.add(nid)
                log.append(RunLogEntry(node_id=nid, node_type=ntype, status="skipped"))
                continue

            upstream_outputs = [ctx["nodes"].get(p) for p in parents[nid]]

            t0 = time.time()
            try:
                output = await _exec_node(
                    user_id=user_id,
                    bot_id=bot_id,
                    node=node,
                    ctx=ctx,
                    upstream_outputs=upstream_outputs,
                )
                ctx["nodes"][nid] = output
                dt = int((time.time() - t0) * 1000)
                log.append(
                    RunLogEntry(
                        node_id=nid,
                        node_type=ntype,
                        status="ok",
                        output=output,
                        duration_ms=dt,
                    )
                )
                if ntype == "condition.if" and isinstance(output, dict) and not output.get("passed"):
                    skipped.add(nid)  # 条件假 → 下游全跳
            except ExecError as e:
                failed = True
                err_text = str(e)
                dt = int((time.time() - t0) * 1000)
                log.append(
                    RunLogEntry(
                        node_id=nid,
                        node_type=ntype,
                        status="err",
                        error=str(e),
                        duration_ms=dt,
                    )
                )
                break  # 中断执行
            except Exception as e:
                failed = True
                err_text = f"{type(e).__name__}: {e}"
                log.append(
                    RunLogEntry(
                        node_id=nid,
                        node_type=ntype,
                        status="err",
                        error=err_text,
                    )
                )
                break
    except ExecError as e:
        failed = True
        err_text = str(e)

    duration_ms = int((time.time() - start) * 1000)
    status = "failed" if failed else "success"
    conn.execute(
        "UPDATE workflow_runs SET status = ?, finished_at = datetime('now'), "
        "duration_ms = ?, log = ?, error = ? WHERE id = ?",
        (
            status,
            duration_ms,
            dump_json([log_entry.__dict__ for log_entry in log]),
            err_text,
            run_id,
        ),
    )
    return RunResult(status=status, log=log, error=err_text, duration_ms=duration_ms)
