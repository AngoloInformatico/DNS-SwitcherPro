from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.app.security.access_auth import AccessSessionStore

from .dependencies import require_access_session, require_bootstrap
from .schemas import AccessLoginPayload, AccessPasswordChangePayload, AccessPasswordSetupPayload

router = APIRouter(prefix="/api/auth")


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        AccessSessionStore.COOKIE_NAME,
        token,
        max_age=AccessSessionStore.TTL_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )


@router.get("/status", dependencies=[Depends(require_bootstrap)])
def auth_status(request: Request) -> dict[str, bool]:
    token = request.cookies.get(AccessSessionStore.COOKIE_NAME)
    return {
        "password_configured": request.app.state.access_password.is_configured(),
        "authenticated": request.app.state.access_sessions.is_valid(token),
    }


@router.post("/setup", dependencies=[Depends(require_bootstrap)])
def setup_password(payload: AccessPasswordSetupPayload, request: Request, response: Response) -> dict[str, bool]:
    try:
        request.app.state.access_password.set_initial(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    token = request.app.state.access_sessions.create()
    _set_session_cookie(response, request, token)
    return {"password_configured": True, "authenticated": True}


@router.post("/login", dependencies=[Depends(require_bootstrap)])
def login(payload: AccessLoginPayload, request: Request, response: Response) -> dict[str, bool]:
    if not request.app.state.access_password.is_configured():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Configurare prima la password di accesso")
    if not request.app.state.access_password.verify(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password non corretta")
    token = request.app.state.access_sessions.create()
    _set_session_cookie(response, request, token)
    return {"password_configured": True, "authenticated": True}


@router.put("/password", dependencies=[Depends(require_access_session)])
def change_password(
    payload: AccessPasswordChangePayload, request: Request, response: Response
) -> dict[str, bool]:
    try:
        request.app.state.access_password.change(payload.current_password, payload.new_password)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    request.app.state.access_sessions.revoke_all()
    token = request.app.state.access_sessions.create()
    _set_session_cookie(response, request, token)
    return {"password_configured": True, "authenticated": True}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    request.app.state.access_sessions.revoke(request.cookies.get(AccessSessionStore.COOKIE_NAME))
    response.delete_cookie(AccessSessionStore.COOKIE_NAME, path="/", samesite="strict")
    return {"authenticated": False}
