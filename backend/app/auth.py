from fastapi import Cookie, Depends, HTTPException, Response, status

from .config import get_settings
from .db import get_conn, row_to_dict
from .security import (
    hash_password,
    parse_session,
    sign_session,
    utc_now_iso,
    verify_password,
)


def bootstrap_default_admin() -> None:
    s = get_settings()
    conn = get_conn()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (s.bootstrap_admin_username,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            (
                s.bootstrap_admin_username,
                hash_password(s.bootstrap_admin_password),
                "管理员",
            ),
        )


def authenticate(username: str, password: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, username, password_hash, display_name FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    conn.execute(
        "UPDATE users SET last_login_at = ? WHERE id = ?",
        (utc_now_iso(), row["id"]),
    )
    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"]}


def set_session_cookie(response: Response, user_id: int) -> None:
    s = get_settings()
    response.set_cookie(
        key=s.session_cookie_name,
        value=sign_session(user_id),
        max_age=s.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=False,
    )


def clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(key=s.session_cookie_name)


def current_user(
    session_cookie: str | None = Cookie(default=None, alias=get_settings().session_cookie_name),
) -> dict:
    user_id = parse_session(session_cookie)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="未登录")
    conn = get_conn()
    row = conn.execute(
        "SELECT id, username, display_name FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    user = row_to_dict(row)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户已失效")
    return user


CurrentUser = Depends(current_user)
