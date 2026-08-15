from __future__ import annotations

import argparse
import os

import uvicorn

from backend.app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Avvia il backend locale di DNS Switcher Pro")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default=os.getenv("DNS_SWITCHER_SESSION_TOKEN", "development-only-token"))
    args = parser.parse_args()
    uvicorn.run(create_app(args.token, development=True), host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()

