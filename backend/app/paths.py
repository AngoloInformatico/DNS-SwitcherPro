from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def work_root() -> Path:
    override = os.getenv("DNS_SWITCHER_WORK_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        local_app_data = Path(os.getenv("LOCALAPPDATA", Path(sys.executable).parent))
        return local_app_data / "DNSSwitcherPro" / "Codex_Work"
    return project_root() / "Codex_Work"


def ensure_work_dirs() -> dict[str, Path]:
    root = work_root()
    paths = {
        "root": root,
        "data": root / "data",
        "logs": root / "logs",
        "temp": root / "temp",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def frontend_dist() -> Path:
    if getattr(sys, "frozen", False):
        bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return bundle / "frontend" / "dist"
    return project_root() / "frontend" / "dist"

