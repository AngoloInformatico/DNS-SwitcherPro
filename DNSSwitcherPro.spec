# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
root = Path(SPECPATH)
hiddenimports = ["playwright.async_api", "webview.platforms.edgechromium"]
a = Analysis(
    [str(root / "desktop" / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "frontend" / "dist"), "frontend/dist"), (str(root / "assets"), "assets")],
    hiddenimports=hiddenimports,
    # pywebview espone hook per molti backend grafici; questa applicazione usa
    # esclusivamente Edge WebView2. Evita di trascinare centinaia di MB di
    # toolkit e librerie multimediali presenti nell'ambiente di build.
    excludes=[
        "Codex_Work", "tests", "kivy", "kivymd", "pygame", "cv2",
        "numpy", "PyQt5", "PIL", "yt_dlp", "matplotlib", "pandas",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DNSSwitcherPro",
    icon=str(root / "assets" / "dns-switcher-pro.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
collection = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="DNSSwitcherPro",
)
