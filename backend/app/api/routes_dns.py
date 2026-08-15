import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .dependencies import require_session
from .schemas import SwitchPayload

router = APIRouter(prefix="/api/dns", dependencies=[Depends(require_session)])


@router.post("/switch", status_code=status.HTTP_202_ACCEPTED)
async def switch_dns(payload: SwitchPayload, request: Request) -> dict[str, str]:
    try:
        request.app.state.operations.start(payload.mode)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "accepted", "mode": payload.mode}


@router.post("/cancel")
async def cancel(request: Request) -> dict[str, str]:
    await request.app.state.operations.cancel()
    return {"status": "cancelling"}


@router.post("/verify")
async def verify(request: Request) -> dict[str, object]:
    settings = request.app.state.settings.get()
    target = request.app.state.operations.status.dns_ip
    if not target:
        target = settings.pihole_ip if settings.last_mode == "pihole" else settings.standard_dns_ip
    ok, message = await request.app.state.operations.verifier.verify(target, asyncio.Event())
    request.app.state.operations.status.last_verification = message
    return {"ok": ok, "message": message}
