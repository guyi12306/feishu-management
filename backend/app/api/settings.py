from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .. import feishu_bots, secrets_store
from ..auth import CurrentUser
from ..config import get_settings
from ..security import mask_secret


router = APIRouter(prefix="/api/settings", tags=["settings"])


# ────── LLM ──────
class LlmIn(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


class LlmOut(BaseModel):
    base_url: str
    model: str
    has_api_key: bool
    api_key_masked: str


def _load_llm(user_id: int) -> LlmOut:
    s = get_settings()
    ns = secrets_store.get_namespace(user_id, "llm")
    api_key = ns.get("api_key")
    return LlmOut(
        base_url=ns.get("base_url") or s.llm_base_url,
        model=ns.get("model") or s.llm_model,
        has_api_key=bool(api_key),
        api_key_masked=mask_secret(api_key) if api_key else "",
    )


@router.get("/llm", response_model=LlmOut)
def get_llm(user: dict = CurrentUser) -> LlmOut:
    return _load_llm(user["id"])


@router.post("/llm", response_model=LlmOut)
def update_llm(payload: LlmIn, user: dict = CurrentUser) -> LlmOut:
    if payload.base_url is not None:
        secrets_store.put(user["id"], "llm", "base_url", payload.base_url.strip())
    if payload.model is not None:
        secrets_store.put(user["id"], "llm", "model", payload.model.strip())
    if payload.api_key is not None:
        secrets_store.put(user["id"], "llm", "api_key", payload.api_key.strip())
    return _load_llm(user["id"])


@router.post("/llm/test")
async def test_llm(user: dict = CurrentUser) -> dict:
    from ..agent.llm import LlmClient

    try:
        client = LlmClient.for_user(user["id"])
        msg = await client.complete(
            [{"role": "user", "content": "请回复一个词:好"}],
            max_tokens=8,
        )
        return {"ok": True, "sample": msg.get("content") or "(空)"}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"LLM 测试失败:{e}")


# ────── 飞书机器人 ──────
class FeishuBotIn(BaseModel):
    name: str = Field(default="未命名机器人", max_length=64)
    app_id: str = Field(default="", max_length=128)
    app_secret: str | None = Field(default=None, max_length=256)
    verification_token: str | None = Field(default=None, max_length=256)
    is_default: bool = False


class FeishuBotOut(BaseModel):
    id: str
    name: str
    app_id: str
    has_app_secret: bool
    app_secret_masked: str
    has_verification_token: bool
    verification_token_masked: str
    is_default: bool


@router.get("/feishu/bots", response_model=list[FeishuBotOut])
def list_feishu_bots(user: dict = CurrentUser) -> list[dict]:
    return feishu_bots.list_bots(user["id"])


@router.post("/feishu/bots", response_model=FeishuBotOut)
def create_feishu_bot(payload: FeishuBotIn, user: dict = CurrentUser) -> dict:
    return feishu_bots.upsert_bot(
        user_id=user["id"],
        bot_id=None,
        name=payload.name,
        app_id=payload.app_id,
        app_secret=payload.app_secret,
        verification_token=payload.verification_token,
        is_default=payload.is_default,
    )


@router.put("/feishu/bots/{bot_id}", response_model=FeishuBotOut)
def update_feishu_bot(bot_id: str, payload: FeishuBotIn, user: dict = CurrentUser) -> dict:
    if not feishu_bots.bot_exists(user["id"], bot_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="机器人配置不存在")
    return feishu_bots.upsert_bot(
        user_id=user["id"],
        bot_id=bot_id,
        name=payload.name,
        app_id=payload.app_id,
        app_secret=payload.app_secret,
        verification_token=payload.verification_token,
        is_default=payload.is_default,
    )


@router.delete("/feishu/bots/{bot_id}")
def delete_feishu_bot(bot_id: str, user: dict = CurrentUser) -> dict:
    feishu_bots.delete_bot(user["id"], bot_id)
    return {"ok": True}


@router.post("/feishu/bots/{bot_id}/test")
async def test_feishu_bot(bot_id: str, user: dict = CurrentUser) -> dict:
    from ..lark_client import LarkClient

    if not feishu_bots.bot_exists(user["id"], bot_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="机器人配置不存在")
    try:
        client = LarkClient.for_user(user["id"], bot_id)
        token = await client.tenant_access_token()
        return {"ok": True, "token_prefix": token[:8] + "..."}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"飞书测试失败:{e}")


# ────── 旧单机器人接口:映射到默认机器人,保持兼容 ──────
class FeishuIn(BaseModel):
    app_id: str | None = None
    app_secret: str | None = None
    verification_token: str | None = None


class FeishuOut(BaseModel):
    app_id: str
    has_app_secret: bool
    app_secret_masked: str
    has_verification_token: bool
    verification_token_masked: str


def _default_feishu_out(user_id: int) -> FeishuOut:
    bots = feishu_bots.list_bots(user_id)
    bot = next((b for b in bots if b["is_default"]), None)
    if bot is None:
        return FeishuOut(
            app_id="",
            has_app_secret=False,
            app_secret_masked="",
            has_verification_token=False,
            verification_token_masked="",
        )
    return FeishuOut(
        app_id=bot["app_id"],
        has_app_secret=bot["has_app_secret"],
        app_secret_masked=bot["app_secret_masked"],
        has_verification_token=bot["has_verification_token"],
        verification_token_masked=bot["verification_token_masked"],
    )


@router.get("/feishu", response_model=FeishuOut)
def get_feishu(user: dict = CurrentUser) -> FeishuOut:
    return _default_feishu_out(user["id"])


@router.post("/feishu", response_model=FeishuOut)
def update_feishu(payload: FeishuIn, user: dict = CurrentUser) -> FeishuOut:
    current = feishu_bots.get_credentials(user["id"], feishu_bots.DEFAULT_BOT_ID)
    feishu_bots.upsert_bot(
        user_id=user["id"],
        bot_id=feishu_bots.DEFAULT_BOT_ID,
        name="默认机器人",
        app_id=payload.app_id if payload.app_id is not None else current.get("app_id", ""),
        app_secret=payload.app_secret,
        verification_token=payload.verification_token,
        is_default=True,
    )
    return _default_feishu_out(user["id"])


@router.post("/feishu/test")
async def test_feishu(user: dict = CurrentUser) -> dict:
    from ..lark_client import LarkClient

    bot_id = feishu_bots.get_default_bot_id(user["id"])
    try:
        client = LarkClient.for_user(user["id"], bot_id)
        token = await client.tenant_access_token()
        return {"ok": True, "token_prefix": token[:8] + "..."}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"飞书测试失败:{e}")
