"""Agent 工具注册与基础设施。

每个工具是一个 async 函数 + JSON schema。`register` 装饰器把它们收进全局表,
Agent 主循环用 `openai_tool_schemas` 渲染 tool list,`all_tools()` 拿映射调用。
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


class ToolError(Exception):
    """工具内部抛出 → 主循环捕获 → 作为 tool result 回写给 LLM,不中断会话。"""


@dataclass
class ToolContext:
    user_id: int
    conversation_id: int
    """每条工具调用都有这两件事:谁、在哪个会话里。"""


ToolFn = Callable[..., Awaitable[Any]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: ToolFn

    def openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def call(self, ctx: ToolContext, **kwargs: Any) -> Any:
        sig = inspect.signature(self.fn)
        if "ctx" in sig.parameters:
            return await self.fn(ctx, **kwargs)
        return await self.fn(**kwargs)


_REGISTRY: dict[str, Tool] = {}


def register(name: str, description: str, parameters: dict) -> Callable[[ToolFn], ToolFn]:
    def deco(fn: ToolFn) -> ToolFn:
        _REGISTRY[name] = Tool(name=name, description=description, parameters=parameters, fn=fn)
        return fn

    return deco


def all_tools() -> dict[str, Tool]:
    # import 副作用注册
    from . import bitable, chat, workflow  # noqa: F401

    return dict(_REGISTRY)


def openai_tool_schemas() -> list[dict]:
    return [t.openai_schema() for t in all_tools().values()]
