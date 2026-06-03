"""OpenAI 兼容 LLM 客户端。

直接用 httpx 走 /chat/completions(同步)和 SSE 流式。
不上 openai 库 —— base_url 切换更灵活,流式协议自己解析。
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from .. import secrets_store
from ..config import get_settings


class LlmError(Exception):
    pass


class LlmClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        if not api_key:
            raise LlmError("LLM API Key 未配置,请在『设置』里填好")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    @classmethod
    def for_user(cls, user_id: int) -> "LlmClient":
        ns = secrets_store.get_namespace(user_id, "llm")
        s = get_settings()
        return cls(
            base_url=ns.get("base_url") or s.llm_base_url,
            api_key=ns.get("api_key") or s.llm_api_key,
            model=ns.get("model") or s.llm_model,
        )

    @classmethod
    def is_configured_for(cls, user_id: int) -> bool:
        ns = secrets_store.get_namespace(user_id, "llm")
        return bool(ns.get("api_key") or get_settings().llm_api_key)

    # ────── 同步 complete ──────
    async def complete(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int | None = None,
    ) -> dict:
        """返回 OpenAI 风格的 choice[0].message dict:{role, content, tool_calls?}"""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=120) as cli:
                r = await cli.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.RequestError as e:
            raise LlmError(f"连接 LLM 失败:{e}") from e
        if r.status_code != 200:
            raise LlmError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise LlmError(f"LLM 返回空 choices: {data}")
        return choices[0]["message"]

    # ────── 流式 ──────
    async def stream(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        temperature: float = 0.4,
    ) -> AsyncIterator[dict]:
        """yield 增量 delta dict;最终一个完成事件 {'finish_reason': ...}。"""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=300) as cli:
                async with cli.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                    },
                    json=body,
                ) as r:
                    if r.status_code != 200:
                        text = (await r.aread()).decode("utf-8", errors="ignore")
                        raise LlmError(f"HTTP {r.status_code}: {text[:300]}")
                    async for raw_line in r.aiter_lines():
                        if not raw_line:
                            continue
                        if raw_line.startswith(":"):
                            continue
                        if not raw_line.startswith("data:"):
                            continue
                        payload = raw_line[5:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta") or {}
                        yield {
                            "delta": delta,
                            "finish_reason": choice.get("finish_reason"),
                        }
        except httpx.RequestError as e:
            raise LlmError(f"连接 LLM 失败:{e}") from e
