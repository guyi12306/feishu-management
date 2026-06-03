import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from .config import get_settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at   TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    title           TEXT NOT NULL DEFAULT '新对话',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversations_user
    ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT,
    tool_calls      TEXT,
    tool_result     TEXT,
    draft_id        INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (draft_id) REFERENCES workflow_drafts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conv
    ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS workflow_drafts (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                 INTEGER NOT NULL,
    name                    TEXT NOT NULL DEFAULT '未命名工作流',
    description             TEXT,
    graph                   TEXT NOT NULL DEFAULT '{"nodes":[],"edges":[],"viewport":{"x":0,"y":0,"zoom":1}}',
    status                  TEXT NOT NULL DEFAULT 'draft',
    applied_target          TEXT,
    bot_id                  TEXT,
    source_conversation_id  INTEGER,
    source_message_id       INTEGER,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    last_applied_at         TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    FOREIGN KEY (source_message_id) REFERENCES messages(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_drafts_user_status
    ON workflow_drafts(user_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS feishu_bots (
    user_id                 INTEGER NOT NULL,
    id                      TEXT NOT NULL,
    name                    TEXT NOT NULL,
    app_id                  TEXT NOT NULL,
    app_secret_enc          BLOB,
    verification_token_enc  BLOB,
    is_default              INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_feishu_bots_user_default
    ON feishu_bots(user_id, is_default);

CREATE TABLE IF NOT EXISTS secrets (
    user_id     INTEGER NOT NULL,
    namespace   TEXT NOT NULL,
    key         TEXT NOT NULL,
    value_enc   BLOB NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, namespace, key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id     INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    status          TEXT NOT NULL,
    trigger         TEXT NOT NULL,
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at     TEXT,
    duration_ms     INTEGER,
    log             TEXT,
    error           TEXT,
    FOREIGN KEY (workflow_id) REFERENCES workflow_drafts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_workflow
    ON workflow_runs(workflow_id, id DESC);
"""


def _connect() -> sqlite3.Connection:
    settings = get_settings()
    db_file = settings.database_file
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


_pool: sqlite3.Connection | None = None


def _ensure_migrations(conn: sqlite3.Connection) -> None:
    draft_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(workflow_drafts)").fetchall()
    }
    if "bot_id" not in draft_cols:
        conn.execute("ALTER TABLE workflow_drafts ADD COLUMN bot_id TEXT")


def get_conn() -> sqlite3.Connection:
    global _pool
    if _pool is None:
        _pool = _connect()
        with _pool:
            _pool.executescript(SCHEMA)
            _ensure_migrations(_pool)
    return _pool


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def parse_json(value: str | None, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
