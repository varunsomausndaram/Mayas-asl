"""System-tray applet — gives Jarvis a home on the desktop.

Requires the ``[tray]`` optional extra (``pystray`` and ``Pillow``). The
applet connects to a running Jarvis server and surfaces:

* Status (green = connected, red = unreachable).
* A quick-ask dialog (opens the system dialog box, sends a one-shot prompt).
* Open the web UI in the default browser.
* Start / stop voice mode in the terminal.
* Quit.
"""

from __future__ import annotations

import asyncio
import threading
import webbrowser

from jarvis.cli.client import JarvisClient


def run_tray(base_url: str, api_key: str) -> None:  # pragma: no cover - UI
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError as exc:
        print(
            "tray mode requires the [tray] extra: pip install 'jarvis-assistant[tray]'\n"
            f"{exc}"
        )
        return

    icon = pystray.Icon("jarvis", _make_icon(Image, ImageDraw, ok=True), "Jarvis")

    def ask(_icon, _item) -> None:
        text = _simple_input_dialog("Ask Jarvis")
        if not text:
            return
        asyncio.run(_one_shot(base_url, api_key, text))

    def open_ui(_icon, _item) -> None:
        webbrowser.open(base_url + "/")

    def quit_app(_icon, _item) -> None:
        _icon.stop()

    def status(_icon, _item) -> None:
        asyncio.run(_refresh_status(icon, base_url, api_key, Image, ImageDraw))

    icon.menu = pystray.Menu(
        pystray.MenuItem("Ask…", ask, default=True),
        pystray.MenuItem("Open Web UI", open_ui),
        pystray.MenuItem("Refresh status", status),
        pystray.MenuItem("Quit", quit_app),
    )

    threading.Thread(
        target=lambda: asyncio.run(_refresh_status(icon, base_url, api_key, Image, ImageDraw)),
        daemon=True,
    ).start()

    icon.run()


async def _one_shot(base_url: str, api_key: str, text: str) -> None:
    async with JarvisClient(base_url, api_key) as c:
        data = await c.chat(text)
        _popup(f"Jarvis:\n\n{data.get('reply', '')}")


async def _refresh_status(icon, base_url: str, api_key: str, Image, ImageDraw) -> None:
    ok = True
    try:
        async with JarvisClient(base_url, api_key, timeout=5) as c:
            await c.health()
    except Exception:
        ok = False
    icon.icon = _make_icon(Image, ImageDraw, ok=ok)
    icon.title = "Jarvis — online" if ok else "Jarvis — offline"


def _make_icon(Image, ImageDraw, *, ok: bool):  # pragma: no cover
    img = Image.new("RGB", (64, 64), "black")
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 56, 56), outline=(30, 215, 255), width=3)
    draw.ellipse((22, 22, 42, 42), fill=(30, 215, 255) if ok else (220, 40, 40))
    return img


def _simple_input_dialog(title: str) -> str:  # pragma: no cover
    try:
        import tkinter as tk
        from tkinter import simpledialog

        root = tk.Tk()
        root.withdraw()
        text = simpledialog.askstring(title, "Your message:")
        root.destroy()
        return text or ""
    except Exception:
        return ""


def _popup(message: str) -> None:  # pragma: no cover
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Jarvis", message)
        root.destroy()
    except Exception:
        print(message)
