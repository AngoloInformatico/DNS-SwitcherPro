from fastapi import APIRouter, Depends, Request

from backend.app import __version__

from .dependencies import require_session

router = APIRouter(prefix="/api", dependencies=[Depends(require_session)])


@router.get("/status")
def status(request: Request) -> dict[str, object]:
    return request.app.state.operations.public_status()


@router.post("/status/refresh")
async def refresh_status(request: Request) -> dict[str, object]:
    return await request.app.state.operations.refresh_router_status()


@router.get("/history")
def history(request: Request) -> list[dict[str, object]]:
    return request.app.state.history.latest()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
