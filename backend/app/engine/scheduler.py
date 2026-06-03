"""APScheduler 包装。

只支持 trigger.schedule(cron)。其它触发器(表格变更)由 webhook 分发执行。
"""
from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..db import get_conn, parse_json
from .executor import ExecError, run_workflow


log = logging.getLogger(__name__)


_scheduler: Optional[AsyncIOScheduler] = None


def start() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        _scheduler.start()
    return _scheduler


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _job_id(workflow_id: int) -> str:
    return f"wf-{workflow_id}"


def _cron_from_graph(graph: dict) -> tuple[str, str] | None:
    """从 graph 抽出第一个 trigger.schedule 节点的 cron / tz。"""
    for n in graph.get("nodes", []):
        if n.get("type") == "trigger.schedule":
            cfg = n.get("config") or {}
            cron = cfg.get("cron")
            tz = cfg.get("tz") or "Asia/Shanghai"
            if cron:
                return cron, tz
    return None


def _has_trigger(graph: dict, trigger_type: str) -> bool:
    return any(n.get("type") == trigger_type for n in graph.get("nodes", []))


def _scheduled_workflow_is_current(user_id: int, workflow_id: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT status, graph FROM workflow_drafts WHERE id = ? AND user_id = ?",
        (workflow_id, user_id),
    ).fetchone()
    if row is None or row["status"] != "applied":
        unregister(workflow_id)
        return False
    graph = parse_json(row["graph"]) or {}
    if not _has_trigger(graph, "trigger.schedule"):
        unregister(workflow_id)
        return False
    return True


async def _job_wrapper(user_id: int, workflow_id: int) -> None:
    if not _scheduled_workflow_is_current(user_id, workflow_id):
        return
    try:
        await run_workflow(
            user_id=user_id,
            workflow_id=workflow_id,
            trigger="schedule",
        )
    except ExecError as e:
        log.info("Scheduled run skipped for workflow %s: %s", workflow_id, e)
    except Exception:
        log.exception("Scheduled run failed for workflow %s", workflow_id)


def register(workflow_id: int, user_id: int, graph: dict) -> dict:
    """注册一个 workflow 到调度;同 id 已存在则替换。返回 {cron, tz, next_run}。"""
    sch = start()
    parsed = _cron_from_graph(graph)
    if parsed is None:
        raise ValueError("工作流没有 trigger.schedule 节点,无法定时触发")
    cron, tz = parsed

    try:
        trigger = CronTrigger.from_crontab(cron, timezone=tz)
    except (ValueError, KeyError) as e:
        raise ValueError(f"cron 表达式无效:{e}")

    job = sch.add_job(
        _job_wrapper,
        trigger=trigger,
        args=[user_id, workflow_id],
        id=_job_id(workflow_id),
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return {
        "cron": cron,
        "tz": tz,
        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
    }


def unregister(workflow_id: int) -> bool:
    if _scheduler is None:
        return False
    sch = _scheduler
    try:
        sch.remove_job(_job_id(workflow_id))
        return True
    except Exception:
        return False


def is_registered(workflow_id: int) -> bool:
    if _scheduler is None:
        return False
    sch = _scheduler
    return sch.get_job(_job_id(workflow_id)) is not None


def next_run_time(workflow_id: int) -> str | None:
    if _scheduler is None:
        return None
    sch = _scheduler
    job = sch.get_job(_job_id(workflow_id))
    if not job or not job.next_run_time:
        return None
    return job.next_run_time.isoformat()


async def restore_all() -> None:
    """startup 时把所有 status=applied 的草稿重新挂到 scheduler。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, user_id, graph FROM workflow_drafts WHERE status = 'applied'"
    ).fetchall()
    for r in rows:
        graph = parse_json(r["graph"]) or {}
        if not _has_trigger(graph, "trigger.schedule"):
            if _has_trigger(graph, "trigger.bitable_change"):
                continue
            log.warning("restore workflow %s skipped: 工作流缺少 trigger 节点", r["id"])
            continue
        try:
            register(r["id"], r["user_id"], graph)
        except Exception as e:
            log.warning("restore workflow %s failed: %s", r["id"], e)
