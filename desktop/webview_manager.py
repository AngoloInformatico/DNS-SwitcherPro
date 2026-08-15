from __future__ import annotations

import socket
import threading
import time
import urllib.request
from collections.abc import Callable

import uvicorn

from backend.app.main import create_app


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LocalApplicationServer:
    def __init__(self, token: str):
        self.token = token
        self.port = free_local_port()
        config = uvicorn.Config(
            create_app(token, development=False),
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, name="dns-switcher-api", daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 10.0, on_wait: Callable[[], None] | None = None) -> None:
        self.thread.start()
        deadline = time.monotonic() + timeout
        request = urllib.request.Request(
            f"{self.url}/api/health", headers={"X-Session-Token": self.token}
        )
        while time.monotonic() < deadline:
            if on_wait:
                on_wait()
            try:
                with urllib.request.urlopen(request, timeout=0.5) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(0.1)
        self.stop()
        raise RuntimeError("Il backend locale non si è avviato entro il tempo previsto")

    def stop(self) -> None:
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(timeout=3)
