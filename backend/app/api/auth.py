from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from ..auth import (
    CurrentUser,
    authenticate,
    clear_session_cookie,
    set_session_cookie,
)
from ..db import get_conn
from ..security import hash_password, verify_password


router = APIRouter(prefix="/api", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


@router.post("/login")
def login(payload: LoginIn, response: Response) -> dict:
    user = authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    set_session_cookie(response, user["id"])
    return {"user": user}


@router.post("/logout")
def logout(response: Response, user: dict = CurrentUser) -> dict:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(user: dict = CurrentUser) -> dict:
    return {"user": user}


@router.post("/change-password")
def change_password(payload: ChangePasswordIn, user: dict = CurrentUser) -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT password_hash FROM users WHERE id = ?",
        (user["id"],),
    ).fetchone()
    if row is None or not verify_password(payload.old_password, row["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="原密码不正确")
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(payload.new_password), user["id"]),
    )
    return {"ok": True}
