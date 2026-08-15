from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Request, status


def require_session(request: Request, x_session_token: str | None = Header(default=None)) -> None:
    expected = request.app.state.session_token
    if not x_session_token or not secrets.compare_digest(x_session_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione locale non valida")

