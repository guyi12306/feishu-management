from __future__ import annotations

from uuid import uuid4

from . import secrets_store
from .config import get_settings
from .db import get_conn
from .security import decrypt_secret, encrypt_secret, mask_secret


DEFAULT_BOT_ID = "default"


def _decrypt(value: bytes | None) -> str | None:
    if not value:
        return None
    return decrypt_secret(bytes(value))


def _encrypt(value: str | None) -> bytes | None:
    if value is None or value == "":
        return None
    return encrypt_secret(value)


def _legacy_values(user_id: int) -> dict[str, str]:
    ns = secrets_store.get_namespace(user_id, "feishu")
    settings = get_settings()
    return {
        "app_id": ns.get("app_id") or settings.feishu_app_id,
        "app_secret": ns.get("app_secret") or settings.feishu_app_secret,
        "verification_token": ns.get("verification_token") or "",
    }


def ensure_default_bot(user_id: int) -> None:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM feishu_bots WHERE user_id = ? AND id = ?",
        (user_id, DEFAULT_BOT_ID),
    ).fetchone()
    if row is not None:
        return
    legacy = _legacy_values(user_id)
    if not legacy["app_id"] and not legacy["app_secret"] and not legacy["verification_token"]:
        return
    conn.execute(
        "INSERT INTO feishu_bots "
        "(user_id, id, name, app_id, app_secret_enc, verification_token_enc, is_default) "
        "VALUES (?, ?, ?, ?, ?, ?, 1)",
        (
            user_id,
            DEFAULT_BOT_ID,
            "默认机器人",
            legacy["app_id"],
            _encrypt(legacy["app_secret"]),
            _encrypt(legacy["verification_token"]),
        ),
    )


def _row_to_public(row) -> dict:
    secret = _decrypt(row["app_secret_enc"])
    token = _decrypt(row["verification_token_enc"])
    return {
        "id": row["id"],
        "name": row["name"],
        "app_id": row["app_id"],
        "has_app_secret": bool(secret),
        "app_secret_masked": mask_secret(secret) if secret else "",
        "has_verification_token": bool(token),
        "verification_token_masked": mask_secret(token) if token else "",
        "is_default": bool(row["is_default"]),
    }


def list_bots(user_id: int) -> list[dict]:
    ensure_default_bot(user_id)
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM feishu_bots WHERE user_id = ? "
        "ORDER BY is_default DESC, updated_at DESC",
        (user_id,),
    ).fetchall()
    return [_row_to_public(r) for r in rows]


def get_public_bot(user_id: int, bot_id: str) -> dict | None:
    ensure_default_bot(user_id)
    row = get_conn().execute(
        "SELECT * FROM feishu_bots WHERE user_id = ? AND id = ?",
        (user_id, bot_id),
    ).fetchone()
    return _row_to_public(row) if row is not None else None


def get_default_bot_id(user_id: int) -> str | None:
    ensure_default_bot(user_id)
    row = get_conn().execute(
        "SELECT id FROM feishu_bots WHERE user_id = ? AND is_default = 1 "
        "ORDER BY updated_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return row["id"] if row is not None else None


def bot_exists(user_id: int, bot_id: str | None) -> bool:
    if not bot_id:
        return True
    ensure_default_bot(user_id)
    row = get_conn().execute(
        "SELECT id FROM feishu_bots WHERE user_id = ? AND id = ?",
        (user_id, bot_id),
    ).fetchone()
    return row is not None


def get_credentials(user_id: int, bot_id: str | None = None) -> dict[str, str]:
    ensure_default_bot(user_id)
    conn = get_conn()
    row = None
    if bot_id:
        row = conn.execute(
            "SELECT * FROM feishu_bots WHERE user_id = ? AND id = ?",
            (user_id, bot_id),
        ).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT * FROM feishu_bots WHERE user_id = ? AND is_default = 1 "
            "ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if row is not None:
        return {
            "bot_id": row["id"],
            "name": row["name"],
            "app_id": row["app_id"],
            "app_secret": _decrypt(row["app_secret_enc"]) or "",
            "verification_token": _decrypt(row["verification_token_enc"]) or "",
        }
    legacy = _legacy_values(user_id)
    return {
        "bot_id": DEFAULT_BOT_ID,
        "name": "默认机器人",
        **legacy,
    }


def list_connection_bots() -> list[dict[str, str | int]]:
    conn = get_conn()
    users = conn.execute("SELECT id FROM users").fetchall()
    for user in users:
        ensure_default_bot(user["id"])

    rows = conn.execute(
        "SELECT user_id, id, name, app_id, app_secret_enc FROM feishu_bots "
        "WHERE app_id <> ''"
    ).fetchall()
    bots: list[dict[str, str | int]] = []
    seen: set[tuple[int, str]] = set()
    for row in rows:
        secret = _decrypt(row["app_secret_enc"])
        if not secret:
            continue
        key = (row["user_id"], row["id"])
        if key in seen:
            continue
        seen.add(key)
        bots.append(
            {
                "user_id": row["user_id"],
                "bot_id": row["id"],
                "name": row["name"],
                "app_id": row["app_id"],
                "app_secret": secret,
            }
        )
    return bots


def upsert_bot(
    *,
    user_id: int,
    bot_id: str | None,
    name: str,
    app_id: str,
    app_secret: str | None = None,
    verification_token: str | None = None,
    is_default: bool = False,
) -> dict:
    ensure_default_bot(user_id)
    conn = get_conn()
    target_id = bot_id or f"bot_{uuid4().hex[:12]}"
    existing = conn.execute(
        "SELECT * FROM feishu_bots WHERE user_id = ? AND id = ?",
        (user_id, target_id),
    ).fetchone()
    current_count = conn.execute(
        "SELECT COUNT(*) AS c FROM feishu_bots WHERE user_id = ?",
        (user_id,),
    ).fetchone()["c"]
    should_default = is_default or current_count == 0
    if should_default:
        conn.execute("UPDATE feishu_bots SET is_default = 0 WHERE user_id = ?", (user_id,))

    if existing is None:
        conn.execute(
            "INSERT INTO feishu_bots "
            "(user_id, id, name, app_id, app_secret_enc, verification_token_enc, is_default) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                target_id,
                name.strip() or "未命名机器人",
                app_id.strip(),
                _encrypt(app_secret),
                _encrypt(verification_token),
                1 if should_default else 0,
            ),
        )
    else:
        secret_enc = existing["app_secret_enc"] if app_secret is None else _encrypt(app_secret)
        token_enc = (
            existing["verification_token_enc"]
            if verification_token is None
            else _encrypt(verification_token)
        )
        conn.execute(
            "UPDATE feishu_bots SET name = ?, app_id = ?, app_secret_enc = ?, "
            "verification_token_enc = ?, is_default = ?, updated_at = datetime('now') "
            "WHERE user_id = ? AND id = ?",
            (
                name.strip() or "未命名机器人",
                app_id.strip(),
                secret_enc,
                token_enc,
                1 if should_default else int(existing["is_default"]),
                user_id,
                target_id,
            ),
        )

    if target_id == DEFAULT_BOT_ID:
        secrets_store.put(user_id, "feishu", "app_id", app_id.strip())
        if app_secret is not None:
            secrets_store.put(user_id, "feishu", "app_secret", app_secret.strip())
        if verification_token is not None:
            secrets_store.put(
                user_id, "feishu", "verification_token", verification_token.strip()
            )
    bot = get_public_bot(user_id, target_id)
    assert bot is not None
    return bot


def delete_bot(user_id: int, bot_id: str) -> None:
    conn = get_conn()
    existing = conn.execute(
        "SELECT is_default FROM feishu_bots WHERE user_id = ? AND id = ?",
        (user_id, bot_id),
    ).fetchone()
    if existing is None:
        return
    conn.execute("DELETE FROM feishu_bots WHERE user_id = ? AND id = ?", (user_id, bot_id))
    conn.execute(
        "UPDATE workflow_drafts SET bot_id = NULL WHERE user_id = ? AND bot_id = ?",
        (user_id, bot_id),
    )
    if existing["is_default"]:
        next_bot = conn.execute(
            "SELECT id FROM feishu_bots WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if next_bot is not None:
            conn.execute(
                "UPDATE feishu_bots SET is_default = 1 WHERE user_id = ? AND id = ?",
                (user_id, next_bot["id"]),
            )
