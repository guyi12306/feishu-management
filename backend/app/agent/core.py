"""Agent 主循环 —— Function Calling 协议。

输入:用户最新一句话 + 历史消息(从 DB 拉)
执行:
  loop:
    LLM(messages + tools) → choice.message
    if tool_calls 为空 → 结束
    else 执行每个 tool_call → 把结果作为 role=tool 消息 append → 继续
最多 MAX_ROUNDS 轮。

返回:produce events 流(供 SSE);非流式调用走 run_blocking 收集所有事件。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

from ..db import dump_json, get_conn, parse_json
from .llm import LlmClient, LlmError
from .prompts import system_message
from .tools import ToolContext, ToolError, all_tools, openai_tool_schemas


MAX_ROUNDS = 8
HISTORY_LIMIT = 30  # 上下文里保留的最近消息数


@dataclass
class AgentEvent:
    """Agent 主循环对外发出的事件,用于驱动 SSE / 持久化。"""

    kind: str  # token | tool_call | tool_result | message_complete | error | done
    payload: dict


def _build_history(conversation_id: int) -> list[dict]:
    """从 DB 把会话最近 N 条消息转成 OpenAI 风格 messages 数组。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content, tool_calls, tool_result "
        "FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
        (conversation_id, HISTORY_LIMIT),
    ).fetchall()
    rows = list(reversed(rows))

    msgs: list[dict] = []
    for r in rows:
        role = r["role"]
        content = r["content"] or ""
        if role == "user":
            msgs.append({"role": "user", "content": content})
        elif role == "assistant":
            m: dict[str, Any] = {"role": "assistant", "content": content or None}
            tool_calls = parse_json(r["tool_calls"])
            if tool_calls:
                m["tool_calls"] = tool_calls
            msgs.append(m)
        elif role == "tool":
            tool_result = parse_json(r["tool_result"]) or {}
            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_result.get("tool_call_id", ""),
                    "content": json.dumps(
                        tool_result.get("result"), ensure_ascii=False, default=str
                    ),
                }
            )
    return msgs


def _persist_assistant(
    conversation_id: int,
    content: str,
    tool_calls: list | None,
    draft_id: int | None,
) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, role, content, tool_calls, draft_id) "
        "VALUES (?, 'assistant', ?, ?, ?)",
        (conversation_id, content, dump_json(tool_calls) if tool_calls else None, draft_id),
    )
    return cur.lastrowid


def _persist_tool(
    conversation_id: int, tool_call_id: str, name: str, result: Any, ok: bool
) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, role, tool_result) "
        "VALUES (?, 'tool', ?)",
        (
            conversation_id,
            dump_json(
                {"tool_call_id": tool_call_id, "name": name, "ok": ok, "result": result}
            ),
        ),
    )
    return cur.lastrowid


async def run(
    *,
    user_id: int,
    conversation_id: int,
    user_text: str,
    stream: bool = True,
) -> AsyncIterator[AgentEvent]:
    """主循环;yield 事件。

    调用方负责:在调本函数前 把用户消息已经 INSERT 进 messages 表。
    """
    try:
        llm = LlmClient.for_user(user_id)
    except LlmError as e:
        yield AgentEvent("error", {"message": str(e)})
        return

    ctx = ToolContext(user_id=user_id, conversation_id=conversation_id)
    tool_map = all_tools()
    tool_schemas = openai_tool_schemas()

    messages: list[dict] = [system_message(), *_build_history(conversation_id)]

    for round_idx in range(MAX_ROUNDS):
        # ─── 取一次 LLM 输出(可能含 tool_calls)───
        accumulated_content: list[str] = []
        accumulated_tool_calls: list[dict] = []  # OpenAI 增量协议复原

        if stream:
            try:
                async for chunk in llm.stream(messages, tools=tool_schemas):
                    delta = chunk["delta"]
                    if delta.get("content"):
                        accumulated_content.append(delta["content"])
                        yield AgentEvent("token", {"text": delta["content"]})
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        while len(accumulated_tool_calls) <= idx:
                            accumulated_tool_calls.append(
                                {"id": "", "type": "function",
                                 "function": {"name": "", "arguments": ""}}
                            )
                        slot = accumulated_tool_calls[idx]
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            slot["function"]["arguments"] += fn["arguments"]
                    if chunk.get("finish_reason"):
                        break
            except LlmError as e:
                yield AgentEvent("error", {"message": str(e)})
                return
        else:
            try:
                msg = await llm.complete(messages, tools=tool_schemas)
            except LlmError as e:
                yield AgentEvent("error", {"message": str(e)})
                return
            if msg.get("content"):
                accumulated_content.append(msg["content"])
                yield AgentEvent("token", {"text": msg["content"]})
            accumulated_tool_calls = msg.get("tool_calls") or []

        final_text = "".join(accumulated_content).strip()

        # ─── 没有工具调用 → 收尾 ───
        if not accumulated_tool_calls:
            asst_msg_id = _persist_assistant(conversation_id, final_text, None, None)
            yield AgentEvent(
                "message_complete",
                {"message_id": asst_msg_id, "content": final_text, "draft_id": None},
            )
            yield AgentEvent("done", {})
            return

        # ─── 有工具调用 → 持久化 assistant 消息,然后执行每个 tool ───
        asst_msg_id = _persist_assistant(
            conversation_id, final_text, accumulated_tool_calls, None
        )
        yield AgentEvent(
            "message_complete",
            {"message_id": asst_msg_id, "content": final_text, "draft_id": None},
        )

        messages.append(
            {
                "role": "assistant",
                "content": final_text or None,
                "tool_calls": accumulated_tool_calls,
            }
        )

        created_draft_id: int | None = None
        for tc in accumulated_tool_calls:
            name = tc["function"]["name"]
            raw_args = tc["function"]["arguments"] or "{}"
            tool_call_id = tc.get("id") or ""

            yield AgentEvent(
                "tool_call",
                {"tool_call_id": tool_call_id, "name": name, "arguments_raw": raw_args},
            )

            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError as e:
                err = f"参数 JSON 解析失败:{e}"
                _persist_tool(conversation_id, tool_call_id, name, {"error": err}, ok=False)
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call_id, "content": err}
                )
                yield AgentEvent(
                    "tool_result",
                    {"tool_call_id": tool_call_id, "name": name, "ok": False, "result": err},
                )
                continue

            tool = tool_map.get(name)
            if tool is None:
                err = f"未知工具:{name}"
                _persist_tool(conversation_id, tool_call_id, name, {"error": err}, ok=False)
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call_id, "content": err}
                )
                yield AgentEvent(
                    "tool_result",
                    {"tool_call_id": tool_call_id, "name": name, "ok": False, "result": err},
                )
                continue

            try:
                result = await tool.call(ctx, **args)
                ok = True
            except ToolError as e:
                result = {"error": str(e)}
                ok = False
            except Exception as e:
                result = {"error": f"工具内部异常:{e}"}
                ok = False

            # 工具是 create_draft → 抓 draft_id,挂回到 assistant 消息上
            if ok and name == "create_draft" and isinstance(result, dict):
                created_draft_id = result.get("draft_id")
                if created_draft_id:
                    conn = get_conn()
                    conn.execute(
                        "UPDATE messages SET draft_id = ? WHERE id = ?",
                        (created_draft_id, asst_msg_id),
                    )

            _persist_tool(conversation_id, tool_call_id, name, result, ok=ok)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
            yield AgentEvent(
                "tool_result",
                {"tool_call_id": tool_call_id, "name": name, "ok": ok, "result": result},
            )

        if created_draft_id:
            yield AgentEvent("draft_attached", {"message_id": asst_msg_id, "draft_id": created_draft_id})

    yield AgentEvent("error", {"message": f"超过最大轮次 {MAX_ROUNDS},强行停止"})
    yield AgentEvent("done", {})


async def run_blocking(*, user_id: int, conversation_id: int, user_text: str) -> dict:
    """非流式版本,跑完返回最后一条助手消息 + 可能的 draft_id。"""
    last_content = ""
    last_msg_id: int | None = None
    last_draft_id: int | None = None
    last_error: str | None = None
    async for ev in run(
        user_id=user_id,
        conversation_id=conversation_id,
        user_text=user_text,
        stream=False,
    ):
        if ev.kind == "message_complete":
            last_content = ev.payload.get("content") or last_content
            last_msg_id = ev.payload.get("message_id")
        if ev.kind == "draft_attached":
            last_draft_id = ev.payload.get("draft_id")
        if ev.kind == "error":
            last_error = ev.payload.get("message")
    if last_msg_id is None and last_error:
        last_content = f"LLM 调用失败:{last_error}"
        last_msg_id = _persist_assistant(conversation_id, last_content, None, None)
    return {
        "message_id": last_msg_id,
        "content": last_content,
        "draft_id": last_draft_id,
    }
