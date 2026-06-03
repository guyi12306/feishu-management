"""飞书 IM(群、消息)相关工具。"""
from __future__ import annotations

from ...lark_client import LarkClient, LarkError
from .base import ToolContext, ToolError, register


@register(
    "list_chats",
    "列出当前飞书租户可访问的群聊。返回 [{chat_id, name, description}]。"
    "你在搭工作流需要给某个群发消息时,用这个找到对应群的 chat_id。",
    {"type": "object", "properties": {}, "required": []},
)
async def list_chats(ctx: ToolContext) -> list[dict]:
    try:
        cli = LarkClient.for_user(ctx.user_id)
        return await cli.list_chats()
    except LarkError as e:
        raise ToolError(str(e))
