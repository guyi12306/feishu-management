import os
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

def tearDownModule():
    if db._pool is not None:
        db._pool.close()
        db._pool = None
    _tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
