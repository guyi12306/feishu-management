import os
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


_tmp = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = str(Path(_tmp.name) / "test.db")
os.environ["SESSION_SECRET"] = "test-secret-for-smoke-tests"
os.environ["LLM_API_KEY"] = "test-key"

from fastapi.testclient import TestClient  # noqa: E402

from app.agent.llm import LlmClient, LlmError  # noqa: E402
from app import db  # noqa: E402
from app.engine import executor  # noqa: E402
from app.engine import dispatcher  # noqa: E402
from app.main import app  # noqa: E402


class SmokeTest(unittest.TestCase):
    def test_health_login_and_workflows(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/health").status_code, 200)
            login = client.post(
                "/api/login",
                json={"username": "admin", "password": "admin123"},
            )
            self.assertEqual(login.status_code, 200)
            self.assertEqual(client.get("/api/workflows").status_code, 200)

    def test_chat_llm_error_returns_assistant_message(self):
        with TestClient(app) as client:
            client.post("/api/login", json={"username": "admin", "password": "admin123"})
            with patch.object(LlmClient, "complete", side_effect=LlmError("boom")):
                response = client.post("/api/chat", json={"content": "每天 9 点提醒我发日报"})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["messages"][-1]["role"], "assistant")
            self.assertIn("LLM 调用失败", payload["messages"][-1]["content"])

    def test_bot_mention_dispatch_matches_applied_workflow(self):
        conn = db.get_conn()
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("mention_user", "x"),
        )
        user_id = cur.lastrowid
        graph = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger.bot_mention",
                    "position": {"x": 80, "y": 120},
                    "config": {
                        "bot_id": "bot_a",
                        "chat_type": "全部",
                        "keyword": "report",
                    },
                }
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }
        cur = conn.execute(
            "INSERT INTO workflow_drafts (user_id, name, graph, status) "
            "VALUES (?, ?, ?, 'applied')",
            (user_id, "mention flow", db.dump_json(graph)),
        )
        workflow_id = cur.lastrowid
        event = {
            "message": {
                "chat_type": "group",
                "content": db.dump_json({"text": "@bot report"}),
            }
        }

        hits = dispatcher.find_matching(
            user_id,
            event,
            bot_id="bot_a",
            event_type="im.message.receive_v1",
        )
        misses = dispatcher.find_matching(
            user_id,
            event,
            bot_id="bot_b",
            event_type="im.message.receive_v1",
        )

        self.assertEqual([workflow_id], [hit[0] for hit in hits])
        self.assertEqual([], misses)

    def test_bitable_update_action_calls_lark_client(self):
        conn = db.get_conn()
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("update_user", "x"),
        )
        user_id = cur.lastrowid
        graph = {
            "nodes": [
                {
                    "id": "t1",
                    "type": "trigger.schedule",
                    "position": {"x": 80, "y": 120},
                    "config": {"cron": "0 9 * * *", "tz": "Asia/Shanghai"},
                },
                {
                    "id": "a1",
                    "type": "action.bitable_update",
                    "position": {"x": 360, "y": 120},
                    "config": {
                        "app_token": "app123",
                        "table_id": "tbl123",
                        "record_id": "rec123",
                        "fields": "{\"状态\":\"已处理\"}",
                    },
                },
            ],
            "edges": [{"id": "e1", "source": "t1", "target": "a1"}],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }
        cur = conn.execute(
            "INSERT INTO workflow_drafts (user_id, name, graph, status) "
            "VALUES (?, ?, ?, 'draft')",
            (user_id, "update flow", db.dump_json(graph)),
        )
        workflow_id = cur.lastrowid
        calls = []

        class FakeLarkClient:
            async def update_record(self, app_token, table_id, record_id, fields):
                calls.append((app_token, table_id, record_id, fields))
                return {"record": {"record_id": record_id, "fields": fields}}

        with patch.object(executor.LarkClient, "for_user", return_value=FakeLarkClient()):
            result = asyncio.run(
                executor.run_workflow(
                    user_id=user_id,
                    workflow_id=workflow_id,
                    trigger="manual",
                )
            )

        self.assertEqual(result.status, "success")
        self.assertEqual(
            [("app123", "tbl123", "rec123", {"状态": "已处理"})],
            calls,
        )

def tearDownModule():
    if db._pool is not None:
        db._pool.close()
        db._pool = None
    _tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
