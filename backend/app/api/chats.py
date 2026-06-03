from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from ..auth import CurrentUser
from ..lark_client import LarkClient, LarkError


router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("")
async def list_chats(
    bot_id: str | None = Query(default=None),
    user: dict = CurrentUser,
) -> list[dict]:
    try:
        return await LarkClient.for_user(user["id"], bot_id or None).list_chats()
    except LarkError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
