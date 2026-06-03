from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth as auth_api
from .api import bitables as bitables_api
from .api import chat as chat_api
from .api import settings as settings_api
from .api import webhook as webhook_api
from .api import workflows as workflows_api
from .auth import bootstrap_default_admin
from .config import get_settings
from .db import get_conn
from .engine import scheduler as engine_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_conn()
    bootstrap_default_admin()
    engine_scheduler.start()
    await engine_scheduler.restore_all()
    try:
        yield
    finally:
        engine_scheduler.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Lark Automation Agent",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_api.router)
    app.include_router(bitables_api.router)
    app.include_router(chat_api.router)
    app.include_router(workflows_api.router)
    app.include_router(settings_api.router)
    app.include_router(webhook_api.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app


app = create_app()
