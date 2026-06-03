from __future__ import annotations

from copy import deepcopy
from typing import Any


EVENT_LABELS = {
    "create": "新增",
    "update": "更新",
    "delete": "删除",
}

EVENT_ALIASES = {
    "create": "create",
    "新增": "create",
    "新建": "create",
    "创建": "create",
    "add": "create",
    "insert": "create",
    "update": "update",
    "更新": "update",
    "修改": "update",
    "编辑": "update",
    "modify": "update",
    "edit": "update",
    "delete": "delete",
    "删除": "delete",
    "移除": "delete",
    "remove": "delete",
}


def canonical_event(value: Any, *, default: str = "create") -> str:
    if value is None:
        return default
    raw = str(value).strip()
    return EVENT_ALIASES.get(raw.lower()) or EVENT_ALIASES.get(raw) or default


def localized_event(value: Any, *, default: str = "新增") -> str:
    return EVENT_LABELS.get(canonical_event(value), default)


def localize_graph_events(graph: dict) -> dict:
    localized = deepcopy(graph)
    for node in localized.get("nodes", []) or []:
        if node.get("type") != "trigger.bitable_change":
            continue
        config = node.setdefault("config", {})
        config["event"] = localized_event(config.get("event"))
    return localized
