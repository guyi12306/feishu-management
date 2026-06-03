"""Feishu/Lark event subscription webhook."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from .. import feishu_bots
from ..config import get_settings
from ..db import get_conn
from ..engine import dispatcher


log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["webhook"])


def _find_user_by_app_id(app_id: str) -> tuple[int, str | None] | None:
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

    for row in rows:
        value = decrypt_secret(bytes(row["value_enc"]))
        if value == app_id:
            return row["user_id"], feishu_bots.DEFAULT_BOT_ID

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
    if any(decrypt_secret(bytes(row["value_enc"])) == token for row in legacy_rows):
        return True

    bot_rows = conn.execute(
        "SELECT verification_token_enc FROM feishu_bots "
        "WHERE verification_token_enc IS NOT NULL"
    ).fetchall()
    return any(
        decrypt_secret(bytes(row["verification_token_enc"])) == token
        for row in bot_rows
    )


@router.post("/lark")
async def lark_event(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="非法 JSON")

    if not isinstance(payload, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="payload 必须是对象")

    if payload.get("type") == "url_verification" or (
        "challenge" in payload and payload.get("token")
    ):
        token = payload.get("token", "")
        challenge = payload.get("challenge", "")
        if not _any_token_matches(token):
            log.warning("url_verification token did not match any user")
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="token 不匹配")
        return {"challenge": challenge}

    if "encrypt" in payload and payload.get("type") is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="收到加密 payload，请在飞书事件订阅后台关闭加密",
        )

    header = payload.get("header") or {}
    event_type = header.get("event_type", "")
    token = header.get("token", "")
    app_id = header.get("app_id", "")

    if not event_type:
        log.info("skip payload without event_type: %s", payload)
        return {"ok": True}

    owner = _find_user_by_app_id(app_id)
    if owner is None:
        log.warning("unknown app_id in event: %s", app_id)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="未知 app_id")
    user_id, bot_id = owner

    if not _verify_token(user_id, bot_id, token):
        log.warning("verification token failed for app_id=%s", app_id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="verification_token 不匹配")

    supported_events = dispatcher.BITABLE_CHANGE_EVENTS | dispatcher.MESSAGE_RECEIVE_EVENTS
    if event_type not in supported_events:
        log.info("skip unsupported event_type: %s", event_type)
        return {"ok": True, "skipped": True}

    event = payload.get("event") or {}
    runs = await dispatcher.dispatch(
        user_id,
        event,
        bot_id=bot_id,
        event_type=event_type,
    )
    return {"ok": True, "matched": len(runs), "runs": runs}
