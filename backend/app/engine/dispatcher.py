"""飞书事件 → 触发匹配的工作流。

匹配规则:
- 工作流 status = applied
- 节点 type = trigger.bitable_change
- node.config:
    app_token    必须等于事件里的 file_token / app_token
    table_id     必须等于事件里的 table_id
    event        ∈ {新增, 更新, 删除};旧数据里的 create/update/delete 也兼容。
                 与事件 action_list 里出现的 action 取交集,有交集就匹配

一个事件可能命中多个工作流 → 全部异步并发触发。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..db import get_conn, parse_json
from ..workflow_events import canonical_event
from .executor import run_workflow


log = logging.getLogger(__name__)


def _action_types(event: dict) -> set[str]:
    """飞书 action_list 里每条 action 的类型可能是 create / update / delete,
    或者更细分(action_type 字段)。先粗匹配。"""
    actions = event.get("action_list") or []
    types: set[str] = set()
    for a in actions:
        t = a.get("action_type") or a.get("op") or ""
        if not t:
            continue
        t = t.lower()
        if "create" in t or "add" in t or "insert" in t:
            types.add("create")
        elif "update" in t or "edit" in t or "modify" in t:
            types.add("update")
        elif "delete" in t or "remove" in t:
            types.add("delete")
    # 没明确指标时,按 event_type 兜底
    if not types:
        types.add("update")
    return types


def find_matching(
    user_id: int,
    event: dict,
    *,
    bot_id: str | None = None,
) -> list[tuple[int, dict]]:
    """返回 [(workflow_id, graph), ...]。"""
    file_token = event.get("file_token") or event.get("app_token") or ""
    table_id = event.get("table_id") or ""
    if not file_token or not table_id:
        return []
    seen_actions = _action_types(event)

    conn = get_conn()
    rows = conn.execute(
        "SELECT id, graph, bot_id FROM workflow_drafts "
        "WHERE user_id = ? AND status = 'applied'",
        (user_id,),
    ).fetchall()

    hits: list[tuple[int, dict]] = []
    for r in rows:
        wf_bot_id = r["bot_id"]
        if bot_id and wf_bot_id and wf_bot_id != bot_id:
            continue
        if bot_id and not wf_bot_id and bot_id != "default":
            continue
        graph = parse_json(r["graph"]) or {}
        for n in graph.get("nodes", []):
            if n.get("type") != "trigger.bitable_change":
                continue
            cfg = n.get("config") or {}
            if cfg.get("app_token") != file_token:
                continue
            if cfg.get("table_id") != table_id:
                continue
            ev = canonical_event(cfg.get("event"))
            if ev not in seen_actions:
                continue
            hits.append((r["id"], graph))
            break
    return hits


async def dispatch(user_id: int, event: dict, *, bot_id: str | None = None) -> list[dict]:
    """命中即并发触发;返回每个 run 的简要状态。"""
    hits = find_matching(user_id, event, bot_id=bot_id)
    if not hits:
        return []
    coros = [
        run_workflow(
            user_id=user_id,
            workflow_id=wid,
            trigger="bitable_change",
            trigger_payload=event,
        )
        for wid, _g in hits
    ]
    results = await asyncio.gather(*coros, return_exceptions=True)

    out: list[dict] = []
    for (wid, _g), res in zip(hits, results):
        if isinstance(res, Exception):
            log.exception("dispatch failed for workflow %s", wid)
            out.append({"workflow_id": wid, "status": "failed", "error": str(res)})
        else:
            out.append(
                {
                    "workflow_id": wid,
                    "status": res.status,
                    "duration_ms": res.duration_ms,
                }
            )
    return out
