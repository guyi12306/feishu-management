"""加密键值存储,落到 secrets 表。

按 (user_id, namespace, key) 寻址。namespace 用来分组:
- llm.api_key / llm.base_url / llm.model
- feishu.app_id / feishu.app_secret
"""
from __future__ import annotations

from .db import get_conn
from .security import decrypt_secret, encrypt_secret


def get(user_id: int, namespace: str, key: str) -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT value_enc FROM secrets WHERE user_id = ? AND namespace = ? AND key = ?",
        (user_id, namespace, key),
    ).fetchone()
    if row is None:
        return None
    return decrypt_secret(bytes(row["value_enc"]))


def put(user_id: int, namespace: str, key: str, value: str | None) -> None:
    conn = get_conn()
    if value is None or value == "":
        conn.execute(
            "DELETE FROM secrets WHERE user_id = ? AND namespace = ? AND key = ?",
            (user_id, namespace, key),
        )
        return
    enc = encrypt_secret(value)
    conn.execute(
        "INSERT INTO secrets (user_id, namespace, key, value_enc, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(user_id, namespace, key) DO UPDATE SET "
        "value_enc = excluded.value_enc, updated_at = excluded.updated_at",
        (user_id, namespace, key, enc),
    )


def get_namespace(user_id: int, namespace: str) -> dict[str, str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT key, value_enc FROM secrets WHERE user_id = ? AND namespace = ?",
        (user_id, namespace),
    ).fetchall()
    result: dict[str, str] = {}
    for r in rows:
        v = decrypt_secret(bytes(r["value_enc"]))
        if v is not None:
            result[r["key"]] = v
    return result
