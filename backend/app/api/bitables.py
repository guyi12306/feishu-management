from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ..auth import CurrentUser
from ..lark_client import LarkClient, LarkError


router = APIRouter(prefix="/api/bitables", tags=["bitables"])


class ResolveLinkIn(BaseModel):
    url: str
    bot_id: str | None = None


def _client(user_id: int, bot_id: str | None) -> LarkClient:
    return LarkClient.for_user(user_id, bot_id or None)


def _first_query_value(query: dict[str, list[str]], *names: str) -> str | None:
    for name in names:
        values = query.get(name)
        if values and values[0]:
            return values[0]
    return None


def _parse_bitable_link(value: str) -> dict[str, str | None]:
    text = value.strip()
    if not text:
        return {"kind": None, "token": None, "table_id": None}

    try:
        parsed = urlparse(text)
    except ValueError:
        parsed = urlparse("")

    if parsed.scheme in {"http", "https"} and parsed.netloc:
        parts = [unquote(part) for part in parsed.path.split("/") if part]
        query = parse_qs(parsed.query)
        table_id = _first_query_value(query, "table", "table_id", "tableId")
        for index, part in enumerate(parts):
            if part in {"base", "bitable", "wiki"} and index + 1 < len(parts):
                return {
                    "kind": "wiki" if part == "wiki" else "bitable",
                    "token": parts[index + 1],
                    "table_id": table_id,
                }
        return {"kind": "url", "token": None, "table_id": table_id}

    return {"kind": "bitable", "token": text, "table_id": None}


@router.post("/resolve-link")
async def resolve_bitable_link(
    payload: ResolveLinkIn,
    user: dict = CurrentUser,
) -> dict:
    parsed = _parse_bitable_link(payload.url)
    kind = parsed["kind"]
    token = parsed["token"]
    table_id = parsed["table_id"]

    if kind == "bitable" and token:
        result = {"app_token": token, "source": "bitable"}
        if table_id:
            result["table_id"] = table_id
        return result

    if kind == "wiki" and token:
        try:
            node = await _client(user["id"], payload.bot_id).get_wiki_node(token)
        except LarkError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))

        obj_type = node.get("obj_type") or node.get("type")
        app_token = node.get("obj_token") or node.get("token")
        if obj_type != "bitable" or not app_token:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="这个 Wiki 链接不是多维表格，或当前机器人没有权限读取它",
            )

        result = {
            "app_token": app_token,
            "source": "wiki",
            "name": node.get("title") or node.get("name"),
        }
        if table_id:
            result["table_id"] = table_id
        return result

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail="无法识别这个多维表格链接，请粘贴飞书 /base/ 或 /wiki/ 链接",
    )


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
