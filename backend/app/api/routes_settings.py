from fastapi import APIRouter, Depends, HTTPException, Request

from .dependencies import require_session
from .schemas import ConnectionTestPayload, CredentialsPayload, SettingsPayload

router = APIRouter(prefix="/api/settings", dependencies=[Depends(require_session)])


@router.get("")
def get_settings(request: Request) -> dict[str, object]:
    data = request.app.state.settings.get().public_dict()
    data.pop("last_mode", None)
    return data


@router.put("")
def update_settings(payload: SettingsPayload, request: Request) -> dict[str, object]:
    try:
        updated = request.app.state.settings.update(payload.model_dump())
        data = updated.public_dict()
        data.pop("last_mode", None)
        return data
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/reset")
def reset_settings(request: Request) -> dict[str, object]:
    data = request.app.state.settings.reset().public_dict()
    data.pop("last_mode", None)
    return data


@router.get("/credentials")
def credential_status(request: Request) -> dict[str, object]:
    return request.app.state.credentials.public_status()


@router.put("/credentials")
def update_credentials(payload: CredentialsPayload, request: Request) -> dict[str, object]:
    try:
        request.app.state.credentials.save(payload.username, payload.password)
        return request.app.state.credentials.public_status()
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/test")
async def test_connection(payload: ConnectionTestPayload, request: Request) -> dict[str, object]:
    ok, message = await request.app.state.operations.test_connection(
        payload.target,
        address=payload.address,
        router_protocol=payload.router_protocol,
        router_port=payload.router_port,
        router_timeout=payload.router_timeout,
    )
    return {"ok": ok, "message": message}
