#!/usr/bin/env python3
"""Lightweight IPC helper for the Razer Chroma Omarchy shell plugin."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def get_socket_path() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/omarchy-razer-{os.getuid()}"))
    return runtime / "omarchy-razer-chroma.sock"


def query_daemon(payload: Dict[str, Any], timeout: float = 2.0) -> Dict[str, Any]:
    spath = get_socket_path()
    if not spath.exists():
        return {
            "ok": False,
            "daemonActive": False,
            "openrazerConnected": False,
            "error": "omarchy-razer-chroma daemon is not running",
            "devices": [],
        }
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(spath))
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            chunks = []
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                chunks.append(data)
                if b"\n" in data:
                    break
            raw = b"".join(chunks).decode("utf-8", errors="ignore").strip()
            return json.loads(raw) if raw else {"ok": False, "daemonActive": False, "devices": []}
    except Exception as exc:
        return {
            "ok": False,
            "daemonActive": False,
            "openrazerConnected": False,
            "error": str(exc),
            "devices": [],
        }


def start_services() -> None:
    for svc in ("openrazer-daemon.service", "omarchy-razer-chroma.service"):
        try:
            subprocess.run(
                ["systemctl", "--user", "start", svc],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
        except Exception:
            pass


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "status":
        print(json.dumps(query_daemon({"cmd": "status"})))
        return 0

    action = args[0]
    if action == "start":
        start_services()
        print(json.dumps(query_daemon({"cmd": "rescan"})))
        return 0
    if action == "rescan":
        print(json.dumps(query_daemon({"cmd": "rescan"})))
        return 0
    if action == "power" and len(args) >= 2:
        print(json.dumps(query_daemon({"cmd": "set_enabled", "enabled": args[1] == "on"})))
        return 0
    if action == "mode" and len(args) >= 2:
        print(json.dumps(query_daemon({"cmd": "set_mode", "mode": args[1]})))
        return 0
    if action == "color" and len(args) >= 2:
        target = args[2] if len(args) >= 3 else "all"
        print(json.dumps(query_daemon({"cmd": "set_color", "color": args[1], "target": target})))
        return 0
    if action == "brightness" and len(args) >= 2:
        try:
            level = int(args[1])
        except ValueError:
            level = 85
        print(json.dumps(query_daemon({"cmd": "set_brightness", "brightness": level})))
        return 0
    if action == "reactive" and len(args) >= 2:
        print(json.dumps(query_daemon({"cmd": "set_reactive", "enabled": args[1] == "on"})))
        return 0
    if action == "palette" and len(args) >= 2:
        print(json.dumps(query_daemon({"cmd": "set_palette", "palette": args[1]})))
        return 0
    if action == "preview" and len(args) >= 2:
        print(json.dumps(query_daemon({"cmd": "preview", "state": args[1], "duration": 3.5})))
        return 0

    print(json.dumps(query_daemon({"cmd": "status"})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
