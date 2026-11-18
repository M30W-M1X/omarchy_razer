#!/usr/bin/env python3
"""Omarchy Razer Chroma background daemon.

Controls Razer keyboard & mouse RGB lighting via OpenRazer and drives
Adaptive Lighting animations from AI harness lifecycle events.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Support running as either `python3 -m daemon.razer_chroma_daemon` or directly
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daemon.animations import render_matrix_frame, render_mouse_color
from daemon.devices import RazerController
from daemon.theme import (
    RGB,
    VALID_PALETTES,
    get_palette,
    get_palette_list,
    get_swatches,
    get_theme_idle_rgb,
    hex_to_rgb,
    read_omarchy_theme_colors,
    rgb_to_hex,
    scale_rgb,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("omarchy-razer")

VALID_MODES = ("theme", "static", "breath", "wave", "spectrum", "reactive", "starlight", "off")

# Higher priority wins when multiple AI sessions are active simultaneously
STATE_PRIORITY: Dict[str, int] = {
    "idle": 0,
    "session_start": 10,
    "tool_read": 20,
    "thinking": 30,
    "tool_agent": 40,
    "tool_edit": 50,
    "tool_command": 60,
    "complete": 70,
    "attention": 80,
    "error": 90,
}

# One-shot / decaying states automatically return to idle after their duration
TRANSIENT_DURATIONS: Dict[str, float] = {
    "session_start": 1.6,
    "complete": 3.0,
    "error": 3.2,
    "attention": 6.0,
}

# Safety TTL so a crashed agent never leaves the keyboard stuck animating forever
DEFAULT_SESSION_TTL = 90.0


def config_path() -> Path:
    cfg_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return cfg_home / "omarchy/razer-chroma/config.json"


def state_path() -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state_home / "omarchy/razer-chroma/state.json"


def socket_path() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/omarchy-razer-{os.getuid()}"))
    return runtime / "omarchy-razer-chroma.sock"


@dataclass
class SessionState:
    session_id: str
    source: str
    state: str
    tool: str = ""
    detail: str = ""
    updated_at: float = field(default_factory=time.monotonic)
    started_at: float = field(default_factory=time.monotonic)
    expires_at: float = 0.0


class RazerChromaDaemon:
    def __init__(self) -> None:
        self.controller = RazerController()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()

        self.config: Dict[str, Any] = self._load_config()
        self.sessions: Dict[str, SessionState] = {}
        self.preview_state: Optional[SessionState] = None

        self._active_ai_state: str = "idle"
        self._active_ai_started: float = 0.0
        self._active_ai_source: str = ""
        self._active_ai_tool: str = ""
        self._active_ai_detail: str = ""
        self._manual_dirty: bool = True
        self._last_state_write: float = 0.0
        self._last_theme_mtime: float = self._theme_mtime()
        self._last_aux_draw: Dict[str, float] = {}

    def _default_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "mode": "theme",  # theme | static | breath | wave | spectrum | reactive | starlight | off
            "color": "#7fbbb3",
            "secondaryColor": "#d699b6",
            "keyboardColor": "",  # optional per-device override
            "mouseColor": "",  # optional per-device override
            "brightness": 85,
            "aiReactive": True,
            "palette": "omarchy-theme",
            "fps": 30,
            "sessionTimeoutSec": DEFAULT_SESSION_TTL,
        }

    def _load_config(self) -> Dict[str, Any]:
        cfg = self._default_config()
        path = config_path()
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    cfg.update(loaded)
            except Exception as exc:
                log.warning("Failed loading config %s: %s", path, exc)
        # Validate fields
        if cfg.get("mode") not in VALID_MODES:
            cfg["mode"] = "theme"
        if cfg.get("palette") == "diablo":
            cfg["palette"] = "ember"
        if cfg.get("palette") not in VALID_PALETTES:
            cfg["palette"] = "omarchy-theme"
        cfg["brightness"] = max(0, min(100, int(cfg.get("brightness", 85))))
        cfg["fps"] = max(10, min(60, int(cfg.get("fps", 30))))
        return cfg

    def _save_config(self) -> None:
        path = config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.config, indent=2) + "\n", encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            log.warning("Failed saving config: %s", exc)

    def _theme_mtime(self) -> float:
        theme_colors = Path(
            os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")
        ) / "omarchy/current/theme/colors.toml"
        try:
            return theme_colors.stat().st_mtime
        except OSError:
            return 0.0

    def _resolve_idle_colors(self, device_type: str) -> Tuple[RGB, RGB]:
        mode = self.config["mode"]
        if mode == "theme":
            primary = get_theme_idle_rgb()
            theme_colors = read_omarchy_theme_colors()
            secondary = hex_to_rgb(theme_colors.get("magenta", "#d699b6"), scale_rgb(primary, 0.45))
            return primary, secondary

        override_key = "keyboardColor" if device_type == "keyboard" else "mouseColor"
        override = str(self.config.get(override_key) or "").strip()
        primary = hex_to_rgb(override if override else str(self.config.get("color", "#7fbbb3")))
        secondary = hex_to_rgb(str(self.config.get("secondaryColor", "#d699b6")))
        return primary, secondary

    def _compute_effective_ai_state(self, now: float) -> Tuple[str, float, str, str, str]:
        if not self.config.get("enabled", True) or not self.config.get("aiReactive", True):
            return ("idle", 0.0, "", "", "")

        # Preview takes immediate precedence so the user can test effects anytime
        if self.preview_state is not None:
            if now < self.preview_state.expires_at:
                p = self.preview_state
                return (p.state, p.started_at, p.source, p.tool, p.detail)
            self.preview_state = None

        # Prune expired sessions
        expired = [sid for sid, s in self.sessions.items() if s.expires_at > 0 and now >= s.expires_at]
        for sid in expired:
            del self.sessions[sid]

        if not self.sessions:
            return ("idle", 0.0, "", "", "")

        best = max(
            self.sessions.values(),
            key=lambda s: (STATE_PRIORITY.get(s.state, 0), s.updated_at),
        )
        return (best.state, best.started_at, best.source, best.tool, best.detail)

    def _apply_idle_lighting(self) -> None:
        if not self.controller.ensure_connected():
            return
        enabled = bool(self.config.get("enabled", True))
        mode = str(self.config.get("mode", "theme")) if enabled else "off"
        brightness = int(self.config.get("brightness", 85)) if enabled else 0

        for info in self.controller.get_device_infos():
            primary, secondary = self._resolve_idle_colors(info.device_type)
            self.controller.apply_manual_mode(info.serial, mode, primary, secondary, brightness)
        self._manual_dirty = False

    def _step_ai_animation(self, now: float) -> None:
        if not self.controller.ensure_connected():
            return
        brightness = int(self.config.get("brightness", 85))
        if brightness <= 0 or not self.config.get("enabled", True):
            return

        palette = get_palette(str(self.config.get("palette", "omarchy-theme")))
        primary, secondary = palette.get(self._active_ai_state, palette["thinking"])
        elapsed = max(0.0, now - self._active_ai_started)

        for info in self.controller.get_device_infos():
            # OpenRazer's D-Bus daemon serializes USB HID writes across devices.
            # Drive the keyboard matrix every tick at full hardware FPS and pace
            # auxiliary devices (mice/mats) cleanly so they don't halve keyboard FPS.
            is_primary_kbd = info.device_type == "keyboard"
            if not is_primary_kbd:
                last_aux = self._last_aux_draw.get(info.serial, 0.0)
                if (now - last_aux) < 0.16:
                    continue
                self._last_aux_draw[info.serial] = now

            if info.has_matrix:
                frame = render_matrix_frame(
                    self._active_ai_state,
                    info.matrix_rows,
                    info.matrix_cols,
                    elapsed,
                    primary,
                    secondary,
                )
                self.controller.draw_matrix(info.serial, frame, primary)
            else:
                mouse_rgb = render_mouse_color(self._active_ai_state, elapsed, primary, secondary)
                self.controller.draw_solid_throttled(info.serial, mouse_rgb)

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            now = time.monotonic()
            state, _, source, tool, detail = self._compute_effective_ai_state(now)
            theme_colors = read_omarchy_theme_colors()
            palette_name = str(self.config.get("palette", "omarchy-theme"))
            palette = get_palette(palette_name)
            active_primary = palette.get(state, palette["idle"])[0]
            if state == "idle":
                idle_rgb, _ = self._resolve_idle_colors("keyboard")
                live_hex = "#000000" if (not self.config["enabled"] or self.config["mode"] == "off") else rgb_to_hex(idle_rgb)
            else:
                live_hex = rgb_to_hex(active_primary)

            return {
                "ok": True,
                "daemonActive": True,
                "openrazerInstalled": self.controller.openrazer_installed,
                "openrazerConnected": self.controller.connected,
                "error": self.controller.error_message,
                "devices": self.controller.list_devices(),
                "config": dict(self.config),
                "liveColor": live_hex,
                "ai": {
                    "state": state,
                    "active": state != "idle",
                    "source": source,
                    "tool": tool,
                    "detail": detail,
                    "sessionCount": len(self.sessions),
                    "palette": palette_name,
                },
                "themeColors": theme_colors,
                "palettes": get_palette_list(),
                "swatches": get_swatches(),
            }

    def _write_state_file(self) -> None:
        try:
            path = state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.snapshot()), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass

    def handle_command(self, req: Dict[str, Any]) -> Dict[str, Any]:
        cmd = str(req.get("cmd", "status")).strip()
        with self.lock:
            now = time.monotonic()

            if cmd == "status":
                self.controller.ensure_connected()
                return self.snapshot()

            if cmd == "rescan":
                self.controller.ensure_connected(force=True)
                self._manual_dirty = True
                return self.snapshot()

            if cmd == "set_enabled":
                self.config["enabled"] = bool(req.get("enabled", True))
                self._save_config()
                self._manual_dirty = True
                if self._active_ai_state == "idle" or not self.config["enabled"]:
                    self._apply_idle_lighting()
                return self.snapshot()

            if cmd == "set_mode":
                mode = str(req.get("mode", "theme")).strip().lower()
                if mode not in VALID_MODES:
                    return {"ok": False, "error": f"Invalid mode: {mode}"}
                self.config["mode"] = mode
                if mode != "off":
                    self.config["enabled"] = True
                self._save_config()
                self._manual_dirty = True
                if self._active_ai_state == "idle":
                    self._apply_idle_lighting()
                return self.snapshot()

            if cmd == "set_color":
                raw = str(req.get("color", "")).strip()
                target = str(req.get("target", "all")).strip().lower()
                hex_val = rgb_to_hex(hex_to_rgb(raw))
                if target == "keyboard":
                    self.config["keyboardColor"] = hex_val
                elif target == "mouse":
                    self.config["mouseColor"] = hex_val
                else:
                    self.config["color"] = hex_val
                    self.config["keyboardColor"] = ""
                    self.config["mouseColor"] = ""
                if self.config["mode"] in ("theme", "off", "wave", "spectrum"):
                    self.config["mode"] = "static"
                self.config["enabled"] = True
                self._save_config()
                self._manual_dirty = True
                if self._active_ai_state == "idle":
                    self._apply_idle_lighting()
                return self.snapshot()

            if cmd == "set_secondary_color":
                raw = str(req.get("color", "")).strip()
                self.config["secondaryColor"] = rgb_to_hex(hex_to_rgb(raw))
                self._save_config()
                self._manual_dirty = True
                if self._active_ai_state == "idle":
                    self._apply_idle_lighting()
                return self.snapshot()

            if cmd == "set_brightness":
                val = max(0, min(100, int(req.get("brightness", 85))))
                self.config["brightness"] = val
                self._save_config()
                self.controller.ensure_connected()
                self.controller.set_brightness(val)
                if val > 0 and not self.config["enabled"]:
                    self.config["enabled"] = True
                    self._manual_dirty = True
                return self.snapshot()

            if cmd == "set_reactive":
                self.config["aiReactive"] = bool(req.get("enabled", True))
                if not self.config["aiReactive"]:
                    self.preview_state = None
                    self._manual_dirty = True
                self._save_config()
                return self.snapshot()

            if cmd == "set_palette":
                pal = str(req.get("palette", "omarchy-theme")).strip().lower()
                if pal == "diablo":
                    pal = "ember"
                if pal not in VALID_PALETTES:
                    return {"ok": False, "error": f"Invalid palette: {pal}"}
                self.config["palette"] = pal
                self._save_config()
                return self.snapshot()

            if cmd == "reload_theme":
                self._last_theme_mtime = self._theme_mtime()
                self._manual_dirty = True
                if self._active_ai_state == "idle":
                    self._apply_idle_lighting()
                return self.snapshot()

            if cmd == "preview":
                state = str(req.get("state", "thinking")).strip().lower()
                if state not in STATE_PRIORITY or state == "idle":
                    self.preview_state = None
                    self._manual_dirty = True
                    return self.snapshot()
                dur = float(req.get("duration", TRANSIENT_DURATIONS.get(state, 3.5)))
                dur = max(0.5, min(15.0, dur))
                self.preview_state = SessionState(
                    session_id="__preview__",
                    source="preview",
                    state=state,
                    tool=state,
                    detail="Preview effect",
                    updated_at=now,
                    started_at=now,
                    expires_at=now + dur,
                )
                return self.snapshot()

            if cmd == "ai_event":
                state = str(req.get("state", "idle")).strip().lower()
                if state not in STATE_PRIORITY:
                    state = "thinking"
                session_id = str(req.get("session", "default")).strip() or "default"
                source = str(req.get("source", "agy")).strip() or "agy"
                tool = str(req.get("tool", "")).strip()
                detail = str(req.get("detail", "")).strip()[:120]

                if state == "idle":
                    self.sessions.pop(session_id, None)
                    self._manual_dirty = True
                    return {"ok": True, "state": "idle"}

                ttl = TRANSIENT_DURATIONS.get(
                    state,
                    float(self.config.get("sessionTimeoutSec", DEFAULT_SESSION_TTL)),
                )
                prev = self.sessions.get(session_id)
                started_at = prev.started_at if (prev and prev.state == state) else now
                self.sessions[session_id] = SessionState(
                    session_id=session_id,
                    source=source,
                    state=state,
                    tool=tool,
                    detail=detail,
                    updated_at=now,
                    started_at=started_at,
                    expires_at=now + ttl,
                )
                return {"ok": True, "state": state}

            return {"ok": False, "error": f"Unknown command: {cmd}"}

    def _serve_socket(self) -> None:
        spath = socket_path()
        spath.parent.mkdir(parents=True, exist_ok=True)
        if spath.exists():
            try:
                spath.unlink()
            except OSError:
                pass

        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(spath))
        os.chmod(spath, 0o600)
        srv.listen(32)
        srv.settimeout(0.5)
        log.info("Listening on %s", spath)

        try:
            while not self.stop_event.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    conn.settimeout(2.0)
                    chunks: List[bytes] = []
                    while True:
                        data = conn.recv(65536)
                        if not data:
                            break
                        chunks.append(data)
                        if b"\n" in data:
                            break
                    raw = b"".join(chunks).decode("utf-8", errors="ignore").strip()
                    req = json.loads(raw) if raw else {"cmd": "status"}
                    if not isinstance(req, dict):
                        req = {"cmd": "status"}
                    resp = self.handle_command(req)
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                except Exception as exc:
                    try:
                        conn.sendall((json.dumps({"ok": False, "error": str(exc)}) + "\n").encode("utf-8"))
                    except OSError:
                        pass
                finally:
                    try:
                        conn.close()
                    except OSError:
                        pass
        finally:
            try:
                srv.close()
            except OSError:
                pass
            if spath.exists():
                try:
                    spath.unlink()
                except OSError:
                    pass

    def run(self) -> None:
        sock_thread = threading.Thread(target=self._serve_socket, daemon=True)
        sock_thread.start()

        self.controller.ensure_connected(force=True)
        self._apply_idle_lighting()
        self._write_state_file()

        last_theme_check = 0.0
        while not self.stop_event.is_set():
            now = time.monotonic()
            with self.lock:
                # Detect Omarchy theme switches automatically even without hook
                if (now - last_theme_check) >= 2.0:
                    last_theme_check = now
                    mt = self._theme_mtime()
                    if mt != self._last_theme_mtime:
                        self._last_theme_mtime = mt
                        self._manual_dirty = True

                next_state, started_at, source, tool, detail = self._compute_effective_ai_state(now)
                state_changed = next_state != self._active_ai_state
                if state_changed:
                    was_active = self._active_ai_state != "idle"
                    self._active_ai_state = next_state
                    self._active_ai_started = started_at or now
                    self._active_ai_source = source
                    self._active_ai_tool = tool
                    self._active_ai_detail = detail
                    if next_state == "idle" and was_active:
                        self._manual_dirty = True
                    elif next_state != "idle":
                        # Ensure brightness is restored before matrix draw
                        self.controller.ensure_connected()
                        self.controller.set_brightness(int(self.config.get("brightness", 85)))
                else:
                    self._active_ai_source = source
                    self._active_ai_tool = tool
                    self._active_ai_detail = detail

                if self._active_ai_state != "idle":
                    frame_start = time.monotonic()
                    self._step_ai_animation(frame_start)
                    target_dt = 1.0 / float(self.config.get("fps", 30))
                    elapsed_draw = time.monotonic() - frame_start
                    sleep_for = max(0.0, target_dt - elapsed_draw)
                else:
                    if not self.controller.connected:
                        if self.controller.ensure_connected():
                            self._manual_dirty = True
                    if self._manual_dirty:
                        self._apply_idle_lighting()
                    sleep_for = 0.12

                if state_changed or (now - self._last_state_write) >= 1.5:
                    self._last_state_write = now
                    self._write_state_file()

            if sleep_for > 0:
                self.stop_event.wait(sleep_for)

        sock_thread.join(timeout=2.0)


def main() -> None:
    daemon = RazerChromaDaemon()

    def _handle_sig(_signum: int, _frame: Any) -> None:
        daemon.stop_event.set()

    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)
    daemon.run()


if __name__ == "__main__":
    main()
