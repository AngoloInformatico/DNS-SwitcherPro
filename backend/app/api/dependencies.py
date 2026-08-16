from __future__ import annotations

import secrets

from fastapi import Cookie, Header, HTTPException, Request, status

from backend.app.security.access_auth import AccessSessionStore


def require_bootstrap(request: Request, x_session_token: str | None = Header(default=None)) -> None:
    expected = request.app.state.session_token
    if not x_session_token or not secrets.compare_digest(x_session_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Collegamento locale non valido")


def require_access_session(
    request: Request,
    access_token: str | None = Cookie(default=None, alias=AccessSessionStore.COOKIE_NAME),
) -> None:
    if not request.app.state.access_sessions.is_valid(access_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Accesso richiesto")


# Backward-compatible import name for internal modules and integrations.
require_session = require_access_session
