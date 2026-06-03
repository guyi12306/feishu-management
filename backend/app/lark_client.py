"""飞书 OpenAPI 客户端 —— httpx async + tenant_access_token 缓存。

凭证按工作流选择的机器人读取;旧的单机器人配置仍作为默认机器人兼容。
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from . import feishu_bots
from .config import get_settings


class LarkError(Exception):
    """飞书 OpenAPI 调用层错误。"""

    def __init__(self, code: int, msg: str, *, endpoint: str = "") -> None:
        super().__init__(f"[{code}] {msg}" + (f" @ {endpoint}" if endpoint else ""))
        self.code = code
        self.msg = msg
        self.endpoint = endpoint


class LarkClient:
    """单租户飞书客户端。一次请求/会话一份;tenant_access_token 在内部缓存。"""

    def __init__(self, app_id: str, app_secret: str, *, api_base: str | None = None) -> None:
        if not app_id or not app_secret:
            raise LarkError(-1, "飞书 App ID / Secret 未配置,请在『设置』里填好")
        self.app_id = app_id
        self.app_secret = app_secret
        self.api_base = (api_base or get_settings().feishu_api_base).rstrip("/")
        self._token: str | None = None
        self._token_expire_at: float = 0.0

    @classmethod
    def for_user(cls, user_id: int, bot_id: str | None = None) -> "LarkClient":
        values = feishu_bots.get_credentials(user_id, bot_id)
        return cls(
            app_id=values.get("app_id", ""),
            app_secret=values.get("app_secret", ""),
        )

    # ────── token ──────
    async def tenant_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expire_at - 120:
            return self._token
        url = f"{self.api_base}/auth/v3/tenant_access_token/internal"
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret})
        data = r.json()
        if data.get("code") != 0:
            raise LarkError(data.get("code", -1), data.get("msg", "未知错误"), endpoint=url)
        self._token = data["tenant_access_token"]
        self._token_expire_at = now + int(data.get("expire", 7200))
        return self._token

    async def _request(
        self, method: str, path: str, *, params: dict | None = None, json: Any = None
    ) -> dict:
        token = await self.tenant_access_token()
        url = f"{self.api_base}{path}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as cli:
            r = await cli.request(method, url, params=params, json=json, headers=headers)
        try:
            data = r.json()
        except Exception:
            raise LarkError(r.status_code, r.text[:200], endpoint=path)
        if data.get("code") != 0:
            raise LarkError(data.get("code", r.status_code), data.get("msg", "未知错误"), endpoint=path)
        return data.get("data", {})

    # ────── 多维表格 ──────
    async def list_bitables(self, page_size: int = 50) -> list[dict]:
        """列用户/应用能访问的多维表格(走 drive/v1/files,filter type=bitable)。"""
        data = await self._request(
            "GET",
            "/drive/v1/files",
            params={"page_size": page_size},
        )
        files = [
            {
                "app_token": f.get("token"),
                "name": f.get("name"),
                "url": f.get("url"),
                "owner_id": f.get("owner_id"),
            }
            for f in data.get("files", [])
            if f.get("type") == "bitable"
        ]
        return files

    async def list_tables(self, app_token: str) -> list[dict]:
        data = await self._request(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables",
            params={"page_size": 100},
        )
        return [
            {"table_id": t.get("table_id"), "name": t.get("name"), "revision": t.get("revision")}
            for t in data.get("items", [])
        ]

    async def get_table_fields(self, app_token: str, table_id: str) -> list[dict]:
        data = await self._request(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            params={"page_size": 100},
        )
        return [
            {
                "field_id": f.get("field_id"),
                "name": f.get("field_name"),
                "type": f.get("type"),
                "ui_type": f.get("ui_type"),
                "property": f.get("property"),
            }
            for f in data.get("items", [])
        ]

    async def search_records(
        self,
        app_token: str,
        table_id: str,
        *,
        filter_expr: dict | None = None,
        page_size: int = 50,
    ) -> dict:
        body: dict = {"page_size": page_size, "automatic_fields": True}
        if filter_expr:
            body["filter"] = filter_expr
        return await self._request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
            json=body,
        )

    # ────── IM ──────
    async def update_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: dict,
    ) -> dict:
        return await self._request(
            "PUT",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            params={"ignore_consistency_check": "true", "user_id_type": "open_id"},
            json={"fields": fields},
        )

    async def list_chats(self, page_size: int = 50) -> list[dict]:
        data = await self._request(
            "GET",
            "/im/v1/chats",
            params={"page_size": page_size},
        )
        return [
            {
                "chat_id": c.get("chat_id"),
                "name": c.get("name"),
                "description": c.get("description"),
                "tenant_key": c.get("tenant_key"),
            }
            for c in data.get("items", [])
        ]

    async def send_message(
        self, chat_id: str, text: str, *, msg_type: str = "text"
    ) -> dict:
        if msg_type == "text":
            content = {"text": text}
        else:
            content = {"text": text}
        return await self._request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": chat_id,
                "msg_type": msg_type,
                "content": __import__("json").dumps(content, ensure_ascii=False),
            },
        )
