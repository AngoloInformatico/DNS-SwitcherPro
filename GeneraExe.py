"""Build the Windows executable for DNS Switcher Pro.

Run from the repository root with ``python GeneraExe.py``.  Personal data under
Codex_Work and real environment files are deliberately excluded from the
PyInstaller bundle.
"""
from __future__ import annotations

import os
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
REQUIRED_BUILD_MODULES = (
    "PyInstaller",
    "pytest",
    "fastapi",
    "uvicorn",
    "httpx",
    "bs4",
    "keyring",
    "cryptography",
    "webview",
    "playwright",
)


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("$ " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def missing_build_modules() -> list[str]:
    return [name for name in REQUIRED_BUILD_MODULES if importlib.util.find_spec(name) is None]


def find_ready_python() -> list[str] | None:
    """Find an installed project-compatible Python with all build modules."""
    launcher = shutil.which("py")
    if not launcher:
        return None
    module_check = (
        "import importlib.util,sys;"
        f"names={REQUIRED_BUILD_MODULES!r};"
        "sys.exit(0 if all(importlib.util.find_spec(name) for name in names) else 1)"
    )
    for version in ("3.13", "3.12"):
        result = subprocess.run(
            [launcher, f"-{version}", "-B", "-c", module_check],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            return [launcher, f"-{version}"]
    return None


def ensure_build_interpreter() -> int | None:
    """Relaunch with a ready Python when the file association lacks dependencies."""
    missing = missing_build_modules()
    if not missing:
        return None
    ready_python = find_ready_python()
    if ready_python:
        version = ready_python[-1].removeprefix("-")
        print(
            f"Python {sys.version_info.major}.{sys.version_info.minor} non contiene: "
            f"{', '.join(missing)}. Riavvio automatico con Python {version}..."
        )
        return subprocess.run([*ready_python, "-B", str(Path(__file__).resolve())], cwd=ROOT).returncode
    requirements = ROOT / "backend" / "requirements.txt"
    print(
        "Errore: nell'interprete corrente mancano i moduli di build: "
        f"{', '.join(missing)}.\nInstallarli con:\n"
        f'  "{sys.executable}" -m pip install -r "{requirements}" pyinstaller'
    )
    return 2


def main() -> int:
    if os.name != "nt":
        print("Errore: la build dell'eseguibile è supportata solo su Windows.")
        return 2
    if sys.version_info < (3, 12):
        print("Errore: è richiesto Python 3.12 o superiore.")
        return 2
    interpreter_result = ensure_build_interpreter()
    if interpreter_result is not None:
        return interpreter_result
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        print("Errore: installare Node.js LTS (node e npm devono essere nel PATH).")
        return 2
    if not (FRONTEND / "package.json").exists():
        print("Errore: frontend/package.json non trovato.")
        return 2
    try:
        if not (FRONTEND / "node_modules").exists():
            print("Dipendenze frontend mancanti: eseguire npm install...")
            run([npm, "install"], FRONTEND)
        run([npm, "run", "build"], FRONTEND)
        dist = FRONTEND / "dist"
        if not dist.is_dir() or not (dist / "index.html").exists():
            raise RuntimeError("frontend/dist non è stato generato correttamente")
        run([sys.executable, "-m", "compileall", "-q", "backend", "desktop"])
        try:
            run([sys.executable, "-m", "pytest", "-q"], ROOT)
        except subprocess.CalledProcessError:
            print("Test pytest falliti: build interrotta.")
            return 1
        run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "DNSSwitcherPro.spec"], ROOT)
        exe = ROOT / "dist" / "DNSSwitcherPro" / "DNSSwitcherPro.exe"
        if not exe.exists():
            raise RuntimeError("PyInstaller non ha prodotto dist/DNSSwitcherPro/DNSSwitcherPro.exe")
        archive_base = ROOT / "dist" / "DNSSwitcherPro-Portable-1.1.5"
        archive = Path(shutil.make_archive(str(archive_base), "zip", exe.parent.parent, exe.parent.name))
        print(f"Build completata: {exe}")
        print(f"Dimensione: {exe.stat().st_size / 1024 / 1024:.2f} MB")
        print(f"Archivio portabile: {archive}")
        return 0
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Build fallita: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
