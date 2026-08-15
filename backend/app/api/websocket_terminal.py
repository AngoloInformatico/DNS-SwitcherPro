import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/terminal")
async def terminal(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    if not secrets.compare_digest(token, websocket.app.state.session_token):
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

