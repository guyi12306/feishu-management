"""多维表格相关工具。"""
from __future__ import annotations

from ...lark_client import LarkClient, LarkError
from .base import ToolContext, ToolError, register


@register(
    "list_bitables",
    "列出当前飞书租户可访问的多维表格。"
    "无参数。返回 [{app_token, name, url}]。",
    {"type": "object", "properties": {}, "required": []},
)
async def list_bitables(ctx: ToolContext) -> list[dict]:
    try:
        cli = LarkClient.for_user(ctx.user_id)
        return await cli.list_bitables()
    except LarkError as e:
        raise ToolError(str(e))


@register(
    "list_tables",
    "列出某个多维表格(app_token)下的所有数据表。返回 [{table_id, name, revision}]。",
    {
        "type": "object",
        "properties": {
            "app_token": {"type": "string", "description": "多维表格 token,从 list_bitables 拿"},
        },
        "required": ["app_token"],
    },
)
async def list_tables(ctx: ToolContext, app_token: str) -> list[dict]:
    try:
        cli = LarkClient.for_user(ctx.user_id)
        return await cli.list_tables(app_token)
    except LarkError as e:
        raise ToolError(str(e))


@register(
    "get_table_fields",
    "列出某个数据表的所有字段(列)信息。返回 [{field_id, name, type, ui_type}]。"
    "在写入/查询前用这个先看清字段结构。",
    {
        "type": "object",
        "properties": {
            "app_token": {"type": "string"},
            "table_id": {"type": "string"},
        },
        "required": ["app_token", "table_id"],
    },
)
async def get_table_fields(ctx: ToolContext, app_token: str, table_id: str) -> list[dict]:
    try:
        cli = LarkClient.for_user(ctx.user_id)
        return await cli.get_table_fields(app_token, table_id)
    except LarkError as e:
        raise ToolError(str(e))
