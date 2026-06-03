"""对话路由:
- /api/conversations CRUD
- /api/chat        同步入口(无 LLM key → mock;有 key → 走 Agent)
- /api/chat/stream SSE 流式入口(必须 LLM 已配置)
"""
from __future__ import annotations

import asyncio
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..agent import core as agent_core
from ..agent.llm import LlmClient
from ..auth import CurrentUser
from ..db import dump_json, get_conn, parse_json


router = APIRouter(prefix="/api", tags=["chat"])


class MessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant", "tool"]
    content: str | None
    tool_calls: list | None = None
    tool_result: dict | None = None
    draft_id: int | None = None
    created_at: str


class ConversationOut(BaseModel):
    id: int
    title: str
    updated_at: str


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]


class CreateConversationIn(BaseModel):
    title: str | None = None


class ChatIn(BaseModel):
    conversation_id: int | None = None
    content: str = Field(min_length=1, max_length=8000)


def _row_to_message(row) -> MessageOut:
    return MessageOut(
        id=row["id"],
        role=row["role"],
        content=row["content"],
        tool_calls=parse_json(row["tool_calls"]),
        tool_result=parse_json(row["tool_result"]),
        draft_id=row["draft_id"],
        created_at=row["created_at"],
    )


# ────── 会话 CRUD ──────
@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: dict = CurrentUser):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, updated_at FROM conversations "
        "WHERE user_id = ? ORDER BY updated_at DESC LIMIT 200",
        (user["id"],),
    ).fetchall()
    return [ConversationOut(**dict(r)) for r in rows]


@router.post("/conversations", response_model=ConversationOut)
def create_conversation(payload: CreateConversationIn, user: dict = CurrentUser):
    conn = get_conn()
    title = (payload.title or "新对话").strip() or "新对话"
    cur = conn.execute(
        "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
        (user["id"], title),
    )
    row = conn.execute(
        "SELECT id, title, updated_at FROM conversations WHERE id = ?",
        (cur.lastrowid,),
    ).fetchone()
    return ConversationOut(**dict(row))


@router.get("/conversations/{conv_id}", response_model=ConversationDetailOut)
def get_conversation(conv_id: int, user: dict = CurrentUser):
    conn = get_conn()
    conv = conn.execute(
        "SELECT id, title, updated_at FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user["id"]),
    ).fetchone()
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="会话不存在")
    msgs = conn.execute(
        "SELECT id, role, content, tool_calls, tool_result, draft_id, created_at "
        "FROM messages WHERE conversation_id = ? ORDER BY id",
        (conv_id,),
    ).fetchall()
    return ConversationDetailOut(
        id=conv["id"],
        title=conv["title"],
        updated_at=conv["updated_at"],
        messages=[_row_to_message(m) for m in msgs],
    )


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=64)


@router.put("/conversations/{conv_id}", response_model=ConversationOut)
def rename_conversation(conv_id: int, payload: RenameIn, user: dict = CurrentUser):
    conn = get_conn()
    cur = conn.execute(
        "UPDATE conversations SET title = ? WHERE id = ? AND user_id = ?",
        (payload.title.strip(), conv_id, user["id"]),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="会话不存在")
    row = conn.execute(
        "SELECT id, title, updated_at FROM conversations WHERE id = ?",
        (conv_id,),
    ).fetchone()
    return ConversationOut(**dict(row))


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int, user: dict = CurrentUser):
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user["id"]),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return {"ok": True}


# ────── Mock & Agent 共用 ──────
def _ensure_conversation(user_id: int, conv_id: int | None, first_text: str) -> int:
    conn = get_conn()
    if conv_id is None:
        cur = conn.execute(
            "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
            (user_id, first_text[:24] or "新对话"),
        )
        return cur.lastrowid
    row = conn.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return row["id"]


def _persist_user_message(conv_id: int, content: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
        (conv_id, content),
    )
    return cur.lastrowid


def _bump_conversation(conv_id: int) -> None:
    get_conn().execute(
        "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
        (conv_id,),
    )


def _mock_assistant_reply(user_text: str) -> tuple[str, dict | None]:
    text = (
        f"(Mock 回复) 我已读到「{user_text[:40]}{'…' if len(user_text) > 40 else ''}」"
        "。LLM 还没配,这里是 mock。去『设置』填好 API Key 后就是真智能体。"
    )
    keywords = ("每天", "自动", "定时", "工作流", "提醒")
    if any(k in user_text for k in keywords):
        draft_preview = {
            "name": "(Mock) 销售日报自动汇总",
            "description": "每天 09:00 把销售表近 24 小时新增订单汇总发到运维群。",
            "graph": {
                "nodes": [
                    {"id": "t1", "type": "trigger.schedule", "position": {"x": 80, "y": 120},
                     "config": {"cron": "0 9 * * *", "tz": "Asia/Shanghai"}},
                    {"id": "a1", "type": "action.bitable_query", "position": {"x": 360, "y": 120},
                     "config": {"app_token": "<待选>", "table_id": "<待选>"}},
                    {"id": "a2", "type": "action.send_message", "position": {"x": 660, "y": 120},
                     "config": {"chat_id": "<待选>", "template": "今日新增 {{nodes.a1.count}} 单"}},
                ],
                "edges": [
                    {"id": "e1", "source": "t1", "target": "a1"},
                    {"id": "e2", "source": "a1", "target": "a2"},
                ],
                "viewport": {"x": 0, "y": 0, "zoom": 1},
            },
        }
        return text, draft_preview
    return text, None


# ────── 同步入口 ──────
@router.post("/chat")
async def chat(payload: ChatIn, user: dict = CurrentUser):
    conv_id = _ensure_conversation(user["id"], payload.conversation_id, payload.content)
    user_msg_id = _persist_user_message(conv_id, payload.content)

    if LlmClient.is_configured_for(user["id"]):
        # 走 Agent(非流式)
        result = await agent_core.run_blocking(
            user_id=user["id"],
            conversation_id=conv_id,
            user_text=payload.content,
        )
        _bump_conversation(conv_id)
        conn = get_conn()
        msgs = conn.execute(
            "SELECT id, role, content, tool_calls, tool_result, draft_id, created_at "
            "FROM messages WHERE conversation_id = ? AND id >= ? ORDER BY id",
            (conv_id, user_msg_id),
        ).fetchall()
        return {
            "conversation_id": conv_id,
            "messages": [_row_to_message(m).model_dump() for m in msgs],
            "mode": "agent",
        }

    # 兜底:Mock
    await asyncio.sleep(0.2)
    reply_text, draft_preview = _mock_assistant_reply(payload.content)
    draft_id: int | None = None
    conn = get_conn()
    if draft_preview is not None:
        cur_d = conn.execute(
            "INSERT INTO workflow_drafts "
            "(user_id, name, description, graph, source_conversation_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                user["id"],
                draft_preview["name"],
                draft_preview["description"],
                dump_json(draft_preview["graph"]),
                conv_id,
            ),
        )
        draft_id = cur_d.lastrowid

    cur_a = conn.execute(
        "INSERT INTO messages (conversation_id, role, content, draft_id) "
        "VALUES (?, 'assistant', ?, ?)",
        (conv_id, reply_text, draft_id),
    )
    asst_msg_id = cur_a.lastrowid

    if draft_id is not None:
        conn.execute(
            "UPDATE workflow_drafts SET source_message_id = ? WHERE id = ?",
            (asst_msg_id, draft_id),
        )

    _bump_conversation(conv_id)

    msgs = conn.execute(
        "SELECT id, role, content, tool_calls, tool_result, draft_id, created_at "
        "FROM messages WHERE id IN (?, ?) ORDER BY id",
        (user_msg_id, asst_msg_id),
    ).fetchall()
    return {
        "conversation_id": conv_id,
        "messages": [_row_to_message(m).model_dump() for m in msgs],
        "mode": "mock",
    }


# ────── 流式入口 ──────
def _sse(event: str, data: dict) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@router.post("/chat/stream")
async def chat_stream(payload: ChatIn, user: dict = CurrentUser):
    if not LlmClient.is_configured_for(user["id"]):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="LLM 未配置,请去『设置』填 API Key,或改用 /api/chat(mock)",
        )

    conv_id = _ensure_conversation(user["id"], payload.conversation_id, payload.content)
    user_msg_id = _persist_user_message(conv_id, payload.content)

    async def gen():
        yield _sse(
            "started",
            {"conversation_id": conv_id, "user_message_id": user_msg_id},
        )
        try:
            async for ev in agent_core.run(
                user_id=user["id"],
                conversation_id=conv_id,
                user_text=payload.content,
                stream=True,
            ):
                yield _sse(ev.kind, ev.payload)
        except Exception as e:
            yield _sse("error", {"message": f"内部错误:{e}"})
        finally:
            _bump_conversation(conv_id)
            yield _sse("done", {})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
