"""
Randan's GPT - entry point.

    python main.py             modern HTML/CSS interface (native window, no browser, no web server)
    python main.py --classic   the older Tk interface (fallback)
"""
import logging
import sys
import traceback

from settings.config import APP_NAME, app_data_dir, resource_path


def _setup_logging() -> None:
    logging.basicConfig(
        filename=str(app_data_dir() / "app.log"), level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _webview2_installed() -> bool:
    """Windows needs the (free, usually preinstalled) Edge WebView2 runtime."""
    if sys.platform != "win32":
        return True
    try:
        import winreg
        for root, sub in ((winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
                          (winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
                          (winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")):
            try:
                with winreg.OpenKey(root, sub) as key:
                    if winreg.QueryValueEx(key, "pv")[0] not in ("", "0.0.0.0"):
                        return True
            except OSError:
                continue
    except ImportError:
        return True
    return False


def run_classic() -> None:
    from ui.app import App
    App().mainloop()


def run_web() -> None:
    import webview
    from backend.bridge import Api
    from backend.winfx import apply_window_style

    api = Api()
    dark = api._settings.get("theme") == "Dark"
    window = webview.create_window(
        APP_NAME, url=resource_path("web/index.html"), js_api=api, width=1380, height=880,
        min_size=(1040, 680), background_color="#030605" if dark else "#e6efe8", text_select=True)
    api._attach_window(window)
    window.events.shown += lambda: apply_window_style(window, dark, resource_path("assets/icon.ico"))
    window.events.closed += api._shutdown
    webview.start(gui="edgechromium" if sys.platform == "win32" else None,
                  storage_path=str(app_data_dir() / "webview"), debug="--debug" in sys.argv)


def _error_box(text: str) -> None:
    try:
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, text)
    except Exception:  # noqa: BLE001
        print(text, file=sys.stderr)


def main() -> None:
    _setup_logging()
    try:
        if "--classic" in sys.argv:
            run_classic()
            return
        try:
            import webview  # noqa: F401
        except ImportError:
            _error_box("The modern interface needs the 'pywebview' package (pip install pywebview).\n"
                       "Starting the classic interface instead.")
            run_classic()
            return
        if not _webview2_installed():
            _error_box("The modern interface needs Microsoft Edge WebView2 (free):\n"
                       "https://developer.microsoft.com/microsoft-edge/webview2/\n\n"
                       "Starting the classic interface instead.")
            run_classic()
            return
        run_web()
    except Exception:  # noqa: BLE001
        logging.exception("Fatal error")
        _error_box("The app crashed:\n\n" + traceback.format_exc()[-1200:])
        sys.exit(1)


if __name__ == "__main__":
    main()
