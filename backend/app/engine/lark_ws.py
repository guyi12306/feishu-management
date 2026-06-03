"""Feishu event subscription over the official long-connection SDK."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from .. import feishu_bots
from ..config import get_settings
from . import dispatcher


log = logging.getLogger(__name__)


class LarkWsManager:
    def __init__(self) -> None:
        self._threads: list[threading.Thread] = []
        self._clients: list[Any] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False
        self._last_error: str | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        mode = (get_settings().feishu_event_mode or "websocket").strip().lower()
        if mode not in {"websocket", "sdk", "both"}:
            log.info("Feishu websocket event receiver disabled: mode=%s", mode)
            return
        if self._started:
            return
        self._loop = loop
        self._last_error = None

        try:
            import lark_oapi as lark  # type: ignore
        except Exception as e:
            self._last_error = f"lark-oapi unavailable: {e}"
            log.warning("lark-oapi is unavailable; websocket events disabled: %s", e)
            return

        bots = feishu_bots.list_connection_bots()
        if not bots:
            self._last_error = "no configured Feishu bots with App Secret"
            log.info("No Feishu bots configured; websocket events not started")
            return

        for bot in bots:
            thread = threading.Thread(
                target=self._run_client,
                args=(lark, bot),
                name=f"feishu-ws-{bot['user_id']}-{bot['bot_id']}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        self._started = bool(self._threads)
        log.info("Started Feishu websocket receivers for %s bot(s)", len(self._threads))

    def shutdown(self) -> None:
        for client in list(self._clients):
            stop = getattr(client, "stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception:
                    log.exception("Failed to stop Feishu websocket client")
        self._clients.clear()
        self._threads.clear()
        self._started = False

    def status(self) -> dict:
        return {
            "mode": get_settings().feishu_event_mode,
            "started": self._started,
            "bots": len(self._threads),
            "last_error": self._last_error,
        }

    def _run_client(self, lark: Any, bot: dict[str, Any]) -> None:
        try:
            try:
                import lark_oapi.ws.client as ws_client_module  # type: ignore

                thread_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(thread_loop)
                ws_client_module.loop = thread_loop
            except Exception:
                pass

            handler = (
                lark.EventDispatcherHandler.builder("", "")
                .register_p2_im_message_receive_v1(
                    lambda data: self._handle_message(lark, bot, data)
                )
                .build()
            )
            client = lark.ws.Client(
                bot["app_id"],
                bot["app_secret"],
                event_handler=handler,
                log_level=getattr(lark.LogLevel, "INFO", None),
            )
            self._clients.append(client)
            client.start()
        except Exception:
            log.exception(
                "Feishu websocket client stopped unexpectedly for bot=%s app_id=%s",
                bot.get("bot_id"),
                bot.get("app_id"),
            )

    def _handle_message(self, lark: Any, bot: dict[str, Any], data: Any) -> None:
        payload = self._payload_from_sdk(lark, data)
        event = payload.get("event") if isinstance(payload.get("event"), dict) else payload
        if not isinstance(event, dict):
            log.warning("Skip Feishu websocket event with invalid payload: %s", payload)
            return
        if self._loop is None:
            log.warning("Skip Feishu websocket event before dispatch loop is ready")
            return

        future = asyncio.run_coroutine_threadsafe(
            dispatcher.dispatch(
                int(bot["user_id"]),
                event,
                bot_id=str(bot["bot_id"]),
                event_type="im.message.receive_v1",
            ),
            self._loop,
        )
        future.add_done_callback(
            lambda done: self._log_dispatch_result(bot, done)
        )

    @staticmethod
    def _payload_from_sdk(lark: Any, data: Any) -> dict:
        try:
            raw = lark.JSON.marshal(data)
        except Exception:
            raw = data
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        if isinstance(raw, dict):
            return raw
        return {}

    @staticmethod
    def _log_dispatch_result(bot: dict[str, Any], future: asyncio.Future) -> None:
        try:
            runs = future.result()
            log.info(
                "Feishu websocket event dispatched for bot=%s matched=%s",
                bot.get("bot_id"),
                len(runs),
            )
        except Exception:
            log.exception("Feishu websocket event dispatch failed for bot=%s", bot.get("bot_id"))


manager = LarkWsManager()
