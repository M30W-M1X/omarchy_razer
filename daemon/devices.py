"""OpenRazer device discovery and lighting control abstraction."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .theme import RGB, rgb_to_hex

log = logging.getLogger("omarchy-razer.devices")

try:
    from openrazer.client import DeviceManager  # type: ignore
    from openrazer.client import constants as razer_constants  # type: ignore

    OPENRAZER_AVAILABLE = True
except Exception:
    DeviceManager = None
    razer_constants = None
    OPENRAZER_AVAILABLE = False


@dataclass
class DeviceInfo:
    serial: str
    name: str
    device_type: str  # "keyboard", "mouse", "mousemat", "headset", "accessory", etc.
    has_matrix: bool = False
    matrix_rows: int = 0
    matrix_cols: int = 0
    capabilities: List[str] = field(default_factory=list)
    brightness: int = 100
    last_color: str = "#7fbbb3"
    battery: Optional[int] = None
    charging: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "serial": self.serial,
            "name": self.name,
            "type": self.device_type,
            "hasMatrix": self.has_matrix,
            "matrixRows": self.matrix_rows,
            "matrixCols": self.matrix_cols,
            "capabilities": list(self.capabilities),
            "brightness": self.brightness,
            "lastColor": self.last_color,
            "battery": self.battery,
            "charging": self.charging,
        }


def _safe_has(dev: Any, cap: str) -> bool:
    try:
        return bool(dev.has(cap))
    except Exception:
        return False


def _color_distance(a: Optional[RGB], b: RGB) -> int:
    if a is None:
        return 999
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


class RazerController:
    """Manages connection to openrazer-daemon and applies effects safely."""

    def __init__(self) -> None:
        self._manager: Any = None
        self._devices: Dict[str, Any] = {}
        self._infos: Dict[str, DeviceInfo] = {}
        self._in_custom_mode: Dict[str, bool] = {}
        self._last_row_bytes: Dict[str, Dict[int, bytes]] = {}
        self._last_static_rgb: Dict[str, RGB] = {}
        self._last_static_ts: Dict[str, float] = {}
        self._last_reconnect_attempt: float = 0.0
        self.error_message: str = ""

    @property
    def openrazer_installed(self) -> bool:
        return OPENRAZER_AVAILABLE

    @property
    def connected(self) -> bool:
        return self._manager is not None and len(self._devices) > 0

    def ensure_connected(self, force: bool = False) -> bool:
        if not OPENRAZER_AVAILABLE:
            self.error_message = "python-openrazer is not installed"
            return False

        now = time.monotonic()
        if not force and self._manager is not None and len(self._devices) > 0:
            return True
        if not force and (now - self._last_reconnect_attempt) < 3.0:
            return len(self._devices) > 0

        self._last_reconnect_attempt = now
        try:
            self._manager = DeviceManager()
            # Keep sync_effects off so we can control keyboard & mouse independently
            try:
                self._manager.sync_effects = False
            except Exception:
                pass
            self._refresh_devices()
            self.error_message = "" if self._devices else "No Razer devices detected by openrazer-daemon"
            return len(self._devices) > 0
        except Exception as exc:
            self._manager = None
            self._devices.clear()
            self._infos.clear()
            self.error_message = f"OpenRazer daemon unavailable: {exc}"
            log.debug("OpenRazer connect failed: %s", exc)
            return False

    def _refresh_devices(self) -> None:
        new_devices: Dict[str, Any] = {}
        new_infos: Dict[str, DeviceInfo] = {}
        if self._manager is None:
            return

        for idx, dev in enumerate(self._manager.devices):
            try:
                serial = str(getattr(dev, "serial", "") or f"razer-{idx}")
                name = str(getattr(dev, "name", "Razer Device"))
                dtype = str(getattr(dev, "type", "unknown")).lower()

                has_matrix = False
                m_rows, m_cols = 0, 0
                try:
                    if hasattr(dev, "fx") and hasattr(dev.fx, "advanced") and _safe_has(dev, "lighting_led_matrix"):
                        m_rows = int(dev.fx.advanced.rows)
                        m_cols = int(dev.fx.advanced.cols)
                        if m_rows > 0 and m_cols > 0:
                            has_matrix = True
                except Exception:
                    has_matrix = False

                caps: List[str] = []
                for cap_name, check in (
                    ("static", "lighting_static"),
                    ("breath_single", "lighting_breath_single"),
                    ("breath_dual", "lighting_breath_dual"),
                    ("wave", "lighting_wave"),
                    ("spectrum", "lighting_spectrum"),
                    ("reactive", "lighting_reactive"),
                    ("starlight", "lighting_starlight_single"),
                    ("none", "lighting_none"),
                    ("brightness", "brightness"),
                ):
                    if _safe_has(dev, check):
                        caps.append(cap_name)
                if has_matrix:
                    caps.append("matrix")

                brightness = 100
                try:
                    if _safe_has(dev, "brightness"):
                        brightness = int(round(float(dev.brightness)))
                    else:
                        zones = self._zones(dev)
                        if zones:
                            brightness = int(round(float(zones[0].brightness)))
                except Exception:
                    brightness = 100

                battery: Optional[int] = None
                charging: Optional[bool] = None
                try:
                    if _safe_has(dev, "battery"):
                        battery = int(round(float(dev.battery_level)))
                        charging = bool(dev.is_charging)
                except Exception:
                    battery = None
                    charging = None

                prev = self._infos.get(serial)
                new_devices[serial] = dev
                new_infos[serial] = DeviceInfo(
                    serial=serial,
                    name=name,
                    device_type=dtype,
                    has_matrix=has_matrix,
                    matrix_rows=m_rows,
                    matrix_cols=m_cols,
                    capabilities=caps,
                    brightness=brightness,
                    last_color=prev.last_color if prev else "#7fbbb3",
                    battery=battery,
                    charging=charging,
                )
            except Exception as exc:
                log.warning("Failed inspecting Razer device: %s", exc)

        self._devices = new_devices
        self._infos = new_infos

    def list_devices(self) -> List[Dict[str, Any]]:
        return [info.to_dict() for info in self._infos.values()]

    def get_device_infos(self) -> List[DeviceInfo]:
        return list(self._infos.values())

    def _zones(self, dev: Any) -> List[Any]:
        zones: List[Any] = []
        misc = getattr(getattr(dev, "fx", None), "misc", None)
        if misc is None:
            return zones
        for zone_name in ("logo", "scroll_wheel", "left", "right", "backlight"):
            z = getattr(misc, zone_name, None)
            if z is not None:
                zones.append(z)
        return zones

    def set_brightness(self, brightness: int, target_serial: Optional[str] = None) -> None:
        brightness = max(0, min(100, int(brightness)))
        for serial, dev in list(self._devices.items()):
            if target_serial and target_serial != "all" and serial != target_serial:
                continue
            try:
                applied = False
                if _safe_has(dev, "brightness"):
                    dev.brightness = float(brightness)
                    applied = True
                for z in self._zones(dev):
                    try:
                        if hasattr(z, "brightness"):
                            z.brightness = float(brightness)
                            applied = True
                    except Exception:
                        pass
                if applied and serial in self._infos:
                    self._infos[serial].brightness = brightness
            except Exception as exc:
                log.debug("set_brightness failed for %s: %s", serial, exc)

    def apply_manual_mode(
        self,
        serial: str,
        mode: str,
        primary: RGB,
        secondary: RGB,
        brightness: int,
    ) -> None:
        dev = self._devices.get(serial)
        info = self._infos.get(serial)
        if dev is None or info is None:
            return

        self._last_static_rgb.pop(serial, None)
        self._in_custom_mode[serial] = False
        self._last_row_bytes.pop(serial, None)
        r, g, b = primary
        r2, g2, b2 = secondary

        try:
            self.set_brightness(brightness, serial)
            if mode == "off" or brightness <= 0:
                self._apply_off(dev)
                info.last_color = "#000000"
                return

            if mode in ("static", "theme"):
                self._apply_static_raw(dev, primary)
                info.last_color = rgb_to_hex(primary)
                return

            if mode == "breath":
                if _safe_has(dev, "lighting_breath_dual"):
                    dev.fx.breath_dual(r, g, b, r2, g2, b2)
                elif _safe_has(dev, "lighting_breath_single"):
                    dev.fx.breath_single(r, g, b)
                else:
                    self._apply_zones(dev, "breath_dual", primary, secondary)
                info.last_color = rgb_to_hex(primary)
                return

            if mode == "wave":
                direction = getattr(razer_constants, "WAVE_RIGHT", 1) if razer_constants else 1
                if _safe_has(dev, "lighting_wave"):
                    dev.fx.wave(direction)
                elif _safe_has(dev, "lighting_spectrum"):
                    dev.fx.spectrum()
                else:
                    self._apply_zones(dev, "wave", primary, secondary)
                info.last_color = rgb_to_hex(primary)
                return

            if mode == "spectrum":
                if _safe_has(dev, "lighting_spectrum"):
                    dev.fx.spectrum()
                else:
                    self._apply_zones(dev, "spectrum", primary, secondary)
                info.last_color = rgb_to_hex(primary)
                return

            if mode == "reactive":
                speed = getattr(razer_constants, "REACTIVE_500MS", 1) if razer_constants else 1
                if _safe_has(dev, "lighting_reactive"):
                    dev.fx.reactive(r, g, b, speed)
                elif self._zones(dev):
                    self._apply_zones(dev, "reactive", primary, secondary)
                elif _safe_has(dev, "lighting_breath_single"):
                    dev.fx.breath_single(r, g, b)
                else:
                    self._apply_static_raw(dev, primary)
                info.last_color = rgb_to_hex(primary)
                return

            if mode == "starlight":
                speed = getattr(razer_constants, "STARLIGHT_FAST", 1) if razer_constants else 1
                if _safe_has(dev, "lighting_starlight_dual"):
                    dev.fx.starlight_dual(r, g, b, r2, g2, b2, speed)
                elif _safe_has(dev, "lighting_starlight_single"):
                    dev.fx.starlight_single(r, g, b, speed)
                elif self._zones(dev):
                    self._apply_zones(dev, "breath_dual", primary, secondary)
                elif _safe_has(dev, "lighting_breath_single"):
                    dev.fx.breath_single(r, g, b)
                else:
                    self._apply_static_raw(dev, primary)
                info.last_color = rgb_to_hex(primary)
                return

            # Fallback
            self._apply_static_raw(dev, primary)
            info.last_color = rgb_to_hex(primary)
        except Exception as exc:
            log.warning("apply_manual_mode(%s, %s) failed: %s", serial, mode, exc)
            self._handle_device_error()

    def draw_matrix(self, serial: str, frame: List[List[RGB]], representative: RGB) -> bool:
        dev = self._devices.get(serial)
        info = self._infos.get(serial)
        if dev is None or info is None or not info.has_matrix:
            return False
        try:
            adv = dev.fx.advanced
            rows = min(info.matrix_rows, len(frame))
            cols = info.matrix_cols
            lighting_dbus = getattr(adv, "_lighting_dbus", None)

            if lighting_dbus is not None:
                prev_rows = self._last_row_bytes.setdefault(serial, {})
                payload = bytearray()
                stop_col = cols - 1
                for r in range(rows):
                    row_data = frame[r]
                    row_buf = bytearray(3 + cols * 3)
                    row_buf[0] = r
                    row_buf[1] = 0
                    row_buf[2] = stop_col
                    pos = 3
                    limit = min(cols, len(row_data))
                    for c in range(limit):
                        rgb = row_data[c]
                        row_buf[pos] = rgb[0]
                        row_buf[pos + 1] = rgb[1]
                        row_buf[pos + 2] = rgb[2]
                        pos += 3
                    row_bytes = bytes(row_buf)
                    if prev_rows.get(r) != row_bytes:
                        prev_rows[r] = row_bytes
                        payload.extend(row_bytes)

                if payload:
                    lighting_dbus.setKeyRow(bytes(payload))
                if not self._in_custom_mode.get(serial, False):
                    lighting_dbus.setCustom()
                    self._in_custom_mode[serial] = True
            else:
                matrix = adv.matrix
                for r in range(rows):
                    row_data = frame[r]
                    c_lim = min(cols, len(row_data))
                    for c in range(c_lim):
                        matrix[r, c] = row_data[c]
                adv.draw()
                self._in_custom_mode[serial] = True

            info.last_color = rgb_to_hex(representative)
            return True
        except Exception as exc:
            log.debug("draw_matrix failed for %s: %s", serial, exc)
            self._handle_device_error()
            return False

    def draw_solid_throttled(self, serial: str, color: RGB, min_interval: float = 0.11) -> None:
        """Update non-matrix devices (e.g. mouse) smoothly without flooding USB."""
        dev = self._devices.get(serial)
        info = self._infos.get(serial)
        if dev is None or info is None:
            return

        now = time.monotonic()
        last_ts = self._last_static_ts.get(serial, 0.0)
        last_rgb = self._last_static_rgb.get(serial)
        if (now - last_ts) < min_interval:
            return
        if _color_distance(last_rgb, color) < 8 and (now - last_ts) < 0.6:
            return

        try:
            if info.has_matrix:
                matrix = dev.fx.advanced.matrix
                for r in range(info.matrix_rows):
                    for c in range(info.matrix_cols):
                        matrix[r, c] = color
                dev.fx.advanced.draw()
            else:
                self._apply_static_raw(dev, color)
            self._last_static_rgb[serial] = color
            self._last_static_ts[serial] = now
            info.last_color = rgb_to_hex(color)
        except Exception as exc:
            log.debug("draw_solid_throttled failed for %s: %s", serial, exc)
            self._handle_device_error()

    def _apply_off(self, dev: Any) -> None:
        if _safe_has(dev, "lighting_none"):
            dev.fx.none()
            return
        if _safe_has(dev, "lighting_static"):
            dev.fx.static(0, 0, 0)
            return
        for z in self._zones(dev):
            try:
                if hasattr(z, "none"):
                    z.none()
                elif hasattr(z, "static"):
                    z.static(0, 0, 0)
            except Exception:
                pass

    def _apply_static_raw(self, dev: Any, color: RGB) -> None:
        r, g, b = color
        if _safe_has(dev, "lighting_static"):
            dev.fx.static(r, g, b)
            return
        applied = False
        for z in self._zones(dev):
            try:
                if hasattr(z, "static"):
                    z.static(r, g, b)
                    applied = True
            except Exception:
                pass
        if not applied and hasattr(dev, "fx") and hasattr(dev.fx, "advanced"):
            try:
                rows = int(dev.fx.advanced.rows)
                cols = int(dev.fx.advanced.cols)
                if rows > 0 and cols > 0:
                    for rr in range(rows):
                        for cc in range(cols):
                            dev.fx.advanced.matrix[rr, cc] = (r, g, b)
                    dev.fx.advanced.draw()
            except Exception:
                pass

    def _apply_zones(self, dev: Any, fx_name: str, primary: RGB, secondary: RGB) -> None:
        r, g, b = primary
        r2, g2, b2 = secondary
        speed = getattr(razer_constants, "REACTIVE_500MS", 1) if razer_constants else 1
        for z in self._zones(dev):
            try:
                if fx_name == "spectrum" and hasattr(z, "spectrum"):
                    z.spectrum()
                elif fx_name == "wave" and hasattr(z, "wave"):
                    z.wave(1)
                elif fx_name == "reactive" and hasattr(z, "reactive"):
                    z.reactive(r, g, b, speed)
                elif fx_name == "breath_dual" and hasattr(z, "breath_dual"):
                    z.breath_dual(r, g, b, r2, g2, b2)
                elif fx_name in ("breath_single", "breath_dual") and hasattr(z, "breath_single"):
                    z.breath_single(r, g, b)
                elif hasattr(z, "static"):
                    z.static(r, g, b)
            except Exception:
                pass

    def _handle_device_error(self) -> None:
        # Force a lazy reconnect on next cycle
        self._manager = None
        self._devices.clear()
        self._in_custom_mode.clear()
        self._last_row_bytes.clear()
