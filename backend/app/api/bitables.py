from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from ..auth import CurrentUser
from ..lark_client import LarkClient, LarkError


router = APIRouter(prefix="/api/bitables", tags=["bitables"])


def _client(user_id: int, bot_id: str | None) -> LarkClient:
    return LarkClient.for_user(user_id, bot_id or None)


@router.get("")
async def list_bitables(
    bot_id: str | None = Query(default=None),
    user: dict = CurrentUser,
) -> list[dict]:
    try:
        return await _client(user["id"], bot_id).list_bitables()
    except LarkError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{app_token}/tables")
async def list_tables(
    app_token: str,
    bot_id: str | None = Query(default=None),
    user: dict = CurrentUser,
) -> list[dict]:
    try:
        return await _client(user["id"], bot_id).list_tables(app_token)
    except LarkError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{app_token}/tables/{table_id}/fields")
async def get_table_fields(
    app_token: str,
    table_id: str,
    bot_id: str | None = Query(default=None),
    user: dict = CurrentUser,
) -> list[dict]:
    try:
        return await _client(user["id"], bot_id).get_table_fields(app_token, table_id)
    except LarkError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
