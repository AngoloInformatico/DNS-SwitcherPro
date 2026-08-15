from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from backend.app.security.secret_masking import mask_secrets


class EventBroker:
    def __init__(self, max_lines: int = 1_000):
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._history: list[dict[str, Any]] = []
        self._max_lines = max_lines

    async def publish(self, level: str, message: str, **data: Any) -> None:
        event = {
            "type": "terminal",
            "timestamp": datetime.now().astimezone().isoformat(),
            "level": level,
            "message": mask_secrets(message),
            **data,
        }
        self._history.append(event)
        if len(self._history) > self._max_lines:
            del self._history[: len(self._history) - self._max_lines]
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1_100)
        for event in self._history:
            queue.put_nowait(event)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def clear(self) -> None:
        self._history.clear()

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

