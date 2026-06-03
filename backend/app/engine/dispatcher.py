"""Dispatch Feishu/Lark events to matching applied workflows."""
from __future__ import annotations

import asyncio
import json
import logging

from ..db import get_conn, parse_json
from ..workflow_events import canonical_event
from .executor import run_workflow


log = logging.getLogger(__name__)


BITABLE_CHANGE_EVENTS = {
    "drive.file.bitable_record_changed_v1",
    "drive.file.bitable.record_changed_v1",
}
MESSAGE_RECEIVE_EVENTS = {"im.message.receive_v1"}


def _action_types(event: dict) -> set[str]:
    actions = event.get("action_list") or []
    types: set[str] = set()
    for action in actions:
        action_type = (action.get("action_type") or action.get("op") or "").lower()
        if not action_type:
            continue
        if "create" in action_type or "add" in action_type or "insert" in action_type:
            types.add("create")
        elif "update" in action_type or "edit" in action_type or "modify" in action_type:
            types.add("update")
        elif "delete" in action_type or "remove" in action_type:
            types.add("delete")
    if not types:
        types.add("update")
    return types


def _message_text(event: dict) -> str:
    message = event.get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return content
        if isinstance(parsed, dict):
            return str(parsed.get("text") or parsed.get("content") or "")
        return content
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "")
    return ""


def _chat_type_matches(expected: str, actual: str) -> bool:
    expected = (expected or "全部").strip()
    actual = (actual or "").strip().lower()
    if expected in ("", "全部"):
        return True
    if expected == "群聊":
        return actual in {"group", "chat", "group_chat"}
    if expected == "私聊":
        return actual in {"p2p", "private", "private_chat"}
    return True


def _workflow_matches_bot(row_bot_id: str | None, bot_id: str | None) -> bool:
    if bot_id and row_bot_id and row_bot_id != bot_id:
        return False
    if bot_id and not row_bot_id and bot_id != "default":
        return False
    return True


def _find_bitable_matching(rows, event: dict, bot_id: str | None) -> list[tuple[int, dict]]:
    file_token = event.get("file_token") or event.get("app_token") or ""
    table_id = event.get("table_id") or ""
    if not file_token or not table_id:
        return []
    seen_actions = _action_types(event)

    hits: list[tuple[int, dict]] = []
    for row in rows:
        if not _workflow_matches_bot(row["bot_id"], bot_id):
            continue
        graph = parse_json(row["graph"]) or {}
        for node in graph.get("nodes", []):
            if node.get("type") != "trigger.bitable_change":
                continue
            config = node.get("config") or {}
            if config.get("app_token") != file_token:
                continue
            if config.get("table_id") != table_id:
                continue
            if canonical_event(config.get("event")) not in seen_actions:
                continue
            hits.append((row["id"], graph))
            break
    return hits


def _find_bot_mention_matching(rows, event: dict, bot_id: str | None) -> list[tuple[int, dict]]:
    message = event.get("message") or {}
    text = _message_text(event)
    chat_type = str(message.get("chat_type") or "")

    hits: list[tuple[int, dict]] = []
    for row in rows:
        if not _workflow_matches_bot(row["bot_id"], bot_id):
            continue
        graph = parse_json(row["graph"]) or {}
        for node in graph.get("nodes", []):
            if node.get("type") != "trigger.bot_mention":
                continue
            config = node.get("config") or {}
            keyword = str(config.get("keyword") or "").strip()
            if keyword and keyword not in text:
                continue
            if not _chat_type_matches(str(config.get("chat_type") or "全部"), chat_type):
                continue
            hits.append((row["id"], graph))
            break
    return hits


def find_matching(
    user_id: int,
    event: dict,
    *,
    bot_id: str | None = None,
    event_type: str | None = None,
) -> list[tuple[int, dict]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, graph, bot_id FROM workflow_drafts "
        "WHERE user_id = ? AND status = 'applied'",
        (user_id,),
    ).fetchall()

    if event_type in MESSAGE_RECEIVE_EVENTS:
        return _find_bot_mention_matching(rows, event, bot_id)
    return _find_bitable_matching(rows, event, bot_id)


async def dispatch(
    user_id: int,
    event: dict,
    *,
    bot_id: str | None = None,
    event_type: str | None = None,
) -> list[dict]:
    hits = find_matching(user_id, event, bot_id=bot_id, event_type=event_type)
    if not hits:
        return []

    trigger = "bot_mention" if event_type in MESSAGE_RECEIVE_EVENTS else "bitable_change"
    coros = [
        run_workflow(
            user_id=user_id,
            workflow_id=workflow_id,
            trigger=trigger,
            trigger_payload=event,
        )
        for workflow_id, _graph in hits
    ]
    results = await asyncio.gather(*coros, return_exceptions=True)

    out: list[dict] = []
    for (workflow_id, _graph), result in zip(hits, results):
        if isinstance(result, Exception):
            log.exception("dispatch failed for workflow %s", workflow_id)
            out.append(
                {
                    "workflow_id": workflow_id,
                    "status": "failed",
                    "error": str(result),
                }
            )
        else:
            out.append(
                {
                    "workflow_id": workflow_id,
                    "status": result.status,
                    "duration_ms": result.duration_ms,
                }
            )
    return out
