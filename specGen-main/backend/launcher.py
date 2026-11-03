"""Entry point of SpecGenerator.exe: starts the local server and opens the browser."""
from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PREFERRED_PORT = 8000


def _is_specgenerator_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/health", timeout=1) as response:
            return response.status == 200 and b"configured" in response.read()
    except OSError:
        return False


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((HOST, port)) != 0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def _open_when_ready(url: str, port: int) -> None:
    for _ in range(60):
        if _is_specgenerator_running(port):
            webbrowser.open(url)
            return
        time.sleep(0.5)


def main() -> None:
    if _is_specgenerator_running(PREFERRED_PORT):
        # Already running (e.g. double-clicked twice): just show it.
        webbrowser.open(f"http://{HOST}:{PREFERRED_PORT}")
        return

    port = PREFERRED_PORT if _port_is_free(PREFERRED_PORT) else _free_port()
    url = f"http://{HOST}:{port}"
    print("SpecGenerator")
    print(f"L'application est disponible sur {url}")
    print("Gardez cette fenêtre ouverte pendant l'utilisation ; fermez-la pour arrêter l'application.")
    sys.stdout.flush()

    # Imported here so the window shows the message above while the app loads.
    from main import app

    threading.Thread(target=_open_when_ready, args=(url, port), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
