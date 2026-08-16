from fastapi import APIRouter, Depends, Request

from backend.app import __version__

from .dependencies import require_bootstrap, require_session

router = APIRouter(prefix="/api")


@router.get("/status", dependencies=[Depends(require_session)])
def status(request: Request) -> dict[str, object]:
    return request.app.state.operations.public_status()


@router.post("/status/refresh", dependencies=[Depends(require_session)])
async def refresh_status(request: Request) -> dict[str, object]:
    return await request.app.state.operations.refresh_router_status()


@router.get("/history", dependencies=[Depends(require_session)])
def history(request: Request) -> list[dict[str, object]]:
    return request.app.state.history.latest()


@router.get("/health", dependencies=[Depends(require_bootstrap)])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
