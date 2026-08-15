from __future__ import annotations

import ctypes
import secrets
import sys
from pathlib import Path
from typing import Any

APP_TITLE = "DNS Switcher Pro"
SPLASH_TITLE = "Avvio DNS Switcher Pro"
MUTEX_NAME = "Local\\DNS-Switcher-Pro-Desktop-v1"


def resource_path(relative: str) -> Path:
    bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return bundle / relative


class SingleInstance:
    """Windows named mutex that also brings the existing window to the front."""

    def __init__(self) -> None:
        self.handle: int | None = None

    def acquire(self) -> bool:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        self.handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not self.handle:
            return False
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            self.focus_existing_window()
            kernel32.CloseHandle(self.handle)
            self.handle = None
            return False
        return True

    @staticmethod
    def focus_existing_window() -> None:
        user32 = ctypes.windll.user32
        for title in (APP_TITLE, SPLASH_TITLE):
            window = user32.FindWindowW(None, title)
            if window:
                user32.ShowWindow(window, 9)  # SW_RESTORE
                user32.SetForegroundWindow(window)
                return

    def release(self) -> None:
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None


class StartupSplash:
    """Small native window displayed before the heavier backend/WebView imports."""

    def __init__(self) -> None:
        self.root: Any = None
        self.status: Any = None
        self._icon_image: Any = None
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.title(SPLASH_TITLE)
            root.configure(bg="#0b1020")
            root.resizable(False, False)
            root.attributes("-topmost", True)
            width, height = 390, 178
            x = max(0, (root.winfo_screenwidth() - width) // 2)
            y = max(0, (root.winfo_screenheight() - height) // 2)
            root.geometry(f"{width}x{height}+{x}+{y}")
            icon = resource_path("assets/dns-switcher-pro.ico")
            if icon.exists():
                root.iconbitmap(default=str(icon))
            png_icon = resource_path("assets/dns-switcher-pro.png")
            if png_icon.exists():
                self._icon_image = tk.PhotoImage(file=str(png_icon))
                root.iconphoto(True, self._icon_image)
            body = tk.Frame(root, bg="#0b1020", padx=28, pady=24)
            body.pack(fill="both", expand=True)
            tk.Label(body, text="DNS SWITCHER", fg="#edf2ff", bg="#0b1020", font=("Segoe UI", 17, "bold")).pack(anchor="w")
            tk.Label(body, text="PRO", fg="#9b7cff", bg="#0b1020", font=("Segoe UI", 10, "bold")).place(x=164, y=7)
            tk.Frame(body, bg="#25304a", height=1).pack(fill="x", pady=(15, 15))
            self.status = tk.Label(body, text="Avvio in corso…", fg="#9aa7bd", bg="#0b1020", font=("Segoe UI", 10))
            self.status.pack(anchor="w")
            tk.Label(body, text="●  Servizio locale protetto", fg="#53d89d", bg="#0b1020", font=("Segoe UI", 8)).pack(anchor="w", pady=(12, 0))
            root.protocol("WM_DELETE_WINDOW", lambda: None)
            root.update_idletasks()
            root.deiconify()
            root.lift()
            root.update()
            self.root = root
        except Exception:
            self.root = None

    def update(self, message: str | None = None) -> None:
        if not self.root:
            return
        try:
            if message and self.status:
                self.status.configure(text=message)
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            self.root = None

    def close(self) -> None:
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
            self.root = None


def main() -> int:
    if sys.platform != "win32":
        print("DNS Switcher Pro richiede Windows 10 o Windows 11.")
        return 1
    instance = SingleInstance()
    if not instance.acquire():
        return 0

    splash = StartupSplash()
    splash.update("Preparazione del servizio locale…")
    try:
        import webview
        from desktop.webview_manager import LocalApplicationServer
    except ImportError:
        splash.close()
        print("pywebview non è installato. Eseguire: pip install -r backend/requirements.txt")
        instance.release()
        return 1

    token = secrets.token_urlsafe(32)
    server = LocalApplicationServer(token)
    try:
        server.start(on_wait=lambda: splash.update("Connessione all'interfaccia…"))
        splash.update("Interfaccia pronta…")
        window = webview.create_window(
            APP_TITLE,
            f"{server.url}/?token={token}",
            width=1180,
            height=820,
            min_size=(860, 650),
            resizable=True,
            background_color="#0b1020",
        )
        window.events.closed += server.stop
        splash.close()
        webview.start(
            gui="edgechromium",
            private_mode=True,
            debug=False,
            icon=str(resource_path("assets/dns-switcher-pro.ico")),
        )
        return 0
    except Exception as exc:
        print(
            "Impossibile avviare DNS Switcher Pro. Verificare che Microsoft Edge WebView2 Runtime "
            f"sia installato. Dettaglio: {exc}"
        )
        return 1
    finally:
        splash.close()
        server.stop()
        instance.release()


if __name__ == "__main__":
    raise SystemExit(main())
