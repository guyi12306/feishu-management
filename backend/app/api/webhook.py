"""飞书事件订阅回调端点。

URL: POST /api/webhook/lark
- 不走 session 鉴权(飞书 server-to-server 调用)
- 必须配置 Verification Token,否则我们直接拒绝
- 支持 url_verification 挑战(老协议 & 加密协议 schema 2.0 通用)
- 暂不解密 encrypt 字段;请在飞书后台关闭加密

事件 → engine.dispatcher 异步分发到所有匹配的工作流(status=applied)。
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from .. import feishu_bots, secrets_store
from ..config import get_settings
from ..db import get_conn
from ..engine import dispatcher


log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["webhook"])


def _find_user_by_app_id(app_id: str) -> tuple[int, str | None] | None:
    """反查哪个用户/机器人配置了这个 app_id;多个匹配取第一个。"""
    if not app_id:
        return None
    conn = get_conn()
    bot = conn.execute(
        "SELECT user_id, id FROM feishu_bots WHERE app_id = ? LIMIT 1",
        (app_id,),
    ).fetchone()
    if bot is not None:
        return bot["user_id"], bot["id"]

    rows = conn.execute(
        "SELECT user_id, value_enc FROM secrets "
        "WHERE namespace = 'feishu' AND key = 'app_id'"
    ).fetchall()
    from ..security import decrypt_secret
    for r in rows:
        v = decrypt_secret(bytes(r["value_enc"]))
        if v == app_id:
            return r["user_id"], feishu_bots.DEFAULT_BOT_ID
    settings = get_settings()
    if settings.feishu_app_id and app_id == settings.feishu_app_id:
        token_users = conn.execute(
            "SELECT DISTINCT user_id FROM secrets "
            "WHERE namespace = 'feishu' AND key = 'verification_token'"
        ).fetchall()
        if len(token_users) == 1:
            return token_users[0]["user_id"], feishu_bots.DEFAULT_BOT_ID
        admin = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (settings.bootstrap_admin_username,),
        ).fetchone()
        if admin is not None:
            return admin["id"], feishu_bots.DEFAULT_BOT_ID
    return None


def _verify_token(user_id: int, bot_id: str | None, token: str) -> bool:
    expected = feishu_bots.get_credentials(user_id, bot_id).get("verification_token")
    return bool(expected) and token == expected


def _any_token_matches(token: str) -> bool:
    conn = get_conn()
    from ..security import decrypt_secret

    legacy_rows = conn.execute(
        "SELECT value_enc FROM secrets WHERE namespace = 'feishu' "
        "AND key = 'verification_token'"
    ).fetchall()
    if any(decrypt_secret(bytes(r["value_enc"])) == token for r in legacy_rows):
        return True

    bot_rows = conn.execute(
        "SELECT verification_token_enc FROM feishu_bots "
        "WHERE verification_token_enc IS NOT NULL"
    ).fetchall()
    return any(
        decrypt_secret(bytes(r["verification_token_enc"])) == token
        for r in bot_rows
    )


@router.post("/lark")
async def lark_event(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="非法 JSON")

    if not isinstance(payload, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="payload 必须是对象")

    # ── 1. url_verification 挑战 ──
    # 飞书在后台配置 webhook URL 时会发一次,要原样回 challenge
    if payload.get("type") == "url_verification" or "challenge" in payload and payload.get("token"):
        token = payload.get("token", "")
        challenge = payload.get("challenge", "")
        # 这次没法定位 user(还没事件 header),允许只要"任意" user 配过该 token 即放行
        if not _any_token_matches(token):
            log.warning("url_verification: token 不匹配任何用户")
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="token 不匹配")
        return {"challenge": challenge}

    # ── 2. 加密事件兜底 ──
    if "encrypt" in payload and payload.get("type") is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="收到加密 payload,请在飞书事件订阅后台关闭加密",
        )

    # ── 3. schema 2.0 事件 ──
    header = payload.get("header") or {}
    event_type = header.get("event_type", "")
    token = header.get("token", "")
    app_id = header.get("app_id", "")

    if not event_type:
        log.info("跳过:无 event_type:%s", payload)
        return {"ok": True}

    owner = _find_user_by_app_id(app_id)
    if owner is None:
        log.warning("收到事件但找不到对应用户 app_id=%s", app_id)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="未知 app_id")
    user_id, bot_id = owner

    if not _verify_token(user_id, bot_id, token):
        log.warning("token 校验失败 app_id=%s", app_id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="verification_token 不匹配")

    # ── 4. 目前我们只处理多维表格变更事件 ──
    if event_type not in {
        "drive.file.bitable_record_changed_v1",
        "drive.file.bitable.record_changed_v1",  # 文档里有几种写法,都接
    }:
        log.info("忽略未订阅的事件类型:%s", event_type)
        return {"ok": True, "skipped": True}

    event = payload.get("event") or {}
    runs = await dispatcher.dispatch(user_id, event, bot_id=bot_id)
    return {"ok": True, "matched": len(runs), "runs": runs}
