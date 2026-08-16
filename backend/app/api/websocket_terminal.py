from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.security.access_auth import AccessSessionStore

router = APIRouter()


@router.websocket("/ws/terminal")
async def terminal(websocket: WebSocket) -> None:
    token = websocket.cookies.get(AccessSessionStore.COOKIE_NAME)
    if not websocket.app.state.access_sessions.is_valid(token):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    queue = websocket.app.state.broker.subscribe()
    try:
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        websocket.app.state.broker.unsubscribe(queue)
