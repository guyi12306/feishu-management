from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_reload: bool = True

    session_secret: str = "dev-only-change-me"
    session_cookie_name: str = "lark_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 30

    database_path: str = "./data/app.db"

    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123"

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_api_base: str = "https://open.feishu.cn/open-apis"
    feishu_event_mode: str = "websocket"

    @property
    def database_file(self) -> Path:
        p = Path(self.database_path)
        if not p.is_absolute():
            p = BACKEND_ROOT / p
        return p

    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
