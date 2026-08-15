"""Build the Windows executable for DNS Switcher Pro.

Run from the repository root with ``python GeneraExe.py``.  Personal data under
Codex_Work and real environment files are deliberately excluded from the
PyInstaller bundle.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("$ " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    if os.name != "nt":
        print("Errore: la build dell'eseguibile è supportata solo su Windows.")
        return 2
    if sys.version_info < (3, 12):
        print("Errore: è richiesto Python 3.12 o superiore.")
        return 2
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
            print("Test pytest non disponibili o falliti: build interrotta.")
            return 1
        if not shutil.which("pyinstaller"):
            print("PyInstaller non installato: installare con 'python -m pip install pyinstaller'.")
            return 2
        run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "DNSSwitcherPro.spec"], ROOT)
        exe = ROOT / "dist" / "DNSSwitcherPro" / "DNSSwitcherPro.exe"
        if not exe.exists():
            raise RuntimeError("PyInstaller non ha prodotto dist/DNSSwitcherPro/DNSSwitcherPro.exe")
        archive_base = ROOT / "dist" / "DNSSwitcherPro-Portable-1.1.3"
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
