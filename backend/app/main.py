from __future__ import annotations

import logging
import os
import secrets
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app import __version__
from backend.app.api import routes_dns, routes_settings, routes_status, websocket_terminal
from backend.app.config.settings_manager import SettingsManager
from backend.app.database.connection import Database
from backend.app.database.repositories import (
    CredentialsRepository,
    HistoryRepository,
    SettingsRepository,
)
from backend.app.paths import ensure_work_dirs, frontend_dist
from backend.app.security.credential_store import CredentialStore
from backend.app.services.events import EventBroker
from backend.app.services.operation_manager import OperationManager


def configure_logging(log_dir: os.PathLike[str]) -> None:
    handler = RotatingFileHandler(
        os.path.join(log_dir, "dns_switcher.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("dns_switcher")
    root.setLevel(logging.INFO)
    if not root.handlers:
        root.addHandler(handler)


def create_app(session_token: str | None = None, development: bool = False) -> FastAPI:
    paths = ensure_work_dirs()
    configure_logging(paths["logs"])
    database = Database(paths["data"] / "dns_switcher.db")
    database.initialize()
    settings_repository = SettingsRepository(database)
    credentials_repository = CredentialsRepository(database)
    history = HistoryRepository(database)
    settings = SettingsManager(settings_repository)
    credentials = CredentialStore(credentials_repository)
    broker = EventBroker()
    operations = OperationManager(settings, credentials, history, broker)

    app = FastAPI(
        title="DNS Switcher Pro Local API",
        version=__version__,
        docs_url="/api/docs" if development else None,
        redoc_url=None,
    )
    app.state.session_token = session_token or os.getenv("DNS_SWITCHER_SESSION_TOKEN") or secrets.token_urlsafe(32)
    app.state.database = database
    app.state.settings = settings
    app.state.credentials = credentials
    app.state.history = history
    app.state.broker = broker
    app.state.operations = operations

    configured_hosts = os.getenv("DNS_SWITCHER_ALLOWED_HOSTS")
    allowed_hosts = (
        [host.strip() for host in configured_hosts.split(",") if host.strip()]
        if configured_hosts else ["127.0.0.1", "localhost", "testserver"]
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    if development:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT"],
            allow_headers=["Content-Type", "X-Session-Token"],
        )

    app.include_router(routes_status.router)
    app.include_router(routes_settings.router)
    app.include_router(routes_dns.router)
    app.include_router(websocket_terminal.router)

    dist = frontend_dist()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    else:
        @app.get("/")
        async def frontend_missing() -> dict[str, str]:
            return {"message": "Frontend non compilato. Eseguire npm run build nella cartella frontend."}

    return app


app = create_app(
    session_token=os.getenv("DNS_SWITCHER_SESSION_TOKEN", "development-only-token"),
    development=os.getenv("DNS_SWITCHER_DEV", "0") == "1",
)
