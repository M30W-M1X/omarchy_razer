"""Omarchy theme reader and AI-reactive color palette resolver."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

RGB = Tuple[int, int, int]

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
TOML_KV_RE = re.compile(r'^\s*([a-zA-Z0-9_]+)\s*=\s*"([^"]+)"')


def clamp_byte(v: float) -> int:
    return max(0, min(255, int(round(v))))


def hex_to_rgb(value: str, fallback: RGB = (127, 187, 179)) -> RGB:
    if not isinstance(value, str):
        return fallback
    m = HEX_RE.match(value.strip())
    if not m:
        return fallback
    h = m.group(1)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(rgb: RGB) -> str:
    r, g, b = (clamp_byte(c) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def blend(c1: RGB, c2: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (
        clamp_byte(c1[0] + (c2[0] - c1[0]) * t),
        clamp_byte(c1[1] + (c2[1] - c1[1]) * t),
        clamp_byte(c1[2] + (c2[2] - c1[2]) * t),
    )


def scale_rgb(c: RGB, factor: float) -> RGB:
    factor = max(0.0, factor)
    return (
        clamp_byte(c[0] * factor),
        clamp_byte(c[1] * factor),
        clamp_byte(c[2] * factor),
    )


def boost_saturation(c: RGB, amount: float = 0.25) -> RGB:
    """Slightly boost saturation so muted terminal themes pop on RGB LEDs."""
    r, g, b = c[0] / 255.0, c[1] / 255.0, c[2] / 255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    if mx == mn or mx == 0:
        return c
    avg = (mx + mn) / 2.0
    r2 = avg + (r - avg) * (1.0 + amount)
    g2 = avg + (g - avg) * (1.0 + amount)
    b2 = avg + (b - avg) * (1.0 + amount)
    return (clamp_byte(r2 * 255), clamp_byte(g2 * 255), clamp_byte(b2 * 255))


def get_omarchy_theme_dir() -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    candidates = [
        state_home / "omarchy/current/theme",
        Path.home() / ".config/omarchy/current/theme",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def read_omarchy_theme_colors() -> Dict[str, str]:
    """Read colors.toml and keyboard.rgb from the active Omarchy theme."""
    theme_dir = get_omarchy_theme_dir()
    colors: Dict[str, str] = {}

    colors_toml = theme_dir / "colors.toml"
    if colors_toml.is_file():
        try:
            for line in colors_toml.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = TOML_KV_RE.match(line)
                if m:
                    key, val = m.group(1).strip(), m.group(2).strip()
                    if HEX_RE.match(val):
                        colors[key] = rgb_to_hex(hex_to_rgb(val))
        except OSError:
            pass

    kb_rgb = theme_dir / "keyboard.rgb"
    if kb_rgb.is_file():
        try:
            raw = kb_rgb.read_text(encoding="utf-8", errors="ignore").strip()
            if HEX_RE.match(raw):
                colors["keyboard_rgb"] = rgb_to_hex(hex_to_rgb(raw))
        except OSError:
            pass

    # Sensible defaults if theme files are missing
    defaults = {
        "accent": "#7fbbb3",
        "background": "#2d353b",
        "foreground": "#d3c6aa",
        "red": "#e67e80",
        "orange": "#e09d7f",
        "yellow": "#dbbc7f",
        "green": "#a7c080",
        "cyan": "#83c092",
        "blue": "#7fbbb3",
        "magenta": "#d699b6",
        "bright_red": "#e67e80",
        "bright_yellow": "#dbbc7f",
        "bright_green": "#a7c080",
        "bright_cyan": "#83c092",
        "bright_blue": "#7fbbb3",
        "bright_magenta": "#d699b6",
    }
    for k, v in defaults.items():
        colors.setdefault(k, v)
    colors.setdefault("keyboard_rgb", colors["accent"])
    return colors


def get_theme_idle_rgb() -> RGB:
    colors = read_omarchy_theme_colors()
    return hex_to_rgb(colors.get("keyboard_rgb") or colors.get("accent", "#7fbbb3"))


def get_palette(palette_name: str) -> Dict[str, Tuple[RGB, RGB]]:
    """Return mapping of AI activity state -> (primary_rgb, secondary_rgb)."""
    if palette_name == "diablo":
        return {
            "idle": ((196, 62, 18), (92, 16, 8)),
            "session_start": ((255, 168, 48), (180, 42, 12)),
            "thinking": ((156, 66, 255), (56, 18, 130)),
            "tool_command": ((255, 92, 12), (255, 200, 42)),
            "tool_edit": ((255, 196, 36), (220, 96, 16)),
            "tool_read": ((48, 178, 255), (18, 68, 168)),
            "tool_agent": ((196, 56, 255), (255, 140, 28)),
            "error": ((255, 12, 16), (110, 0, 6)),
            "attention": ((255, 192, 16), (220, 32, 12)),
            "complete": ((255, 206, 48), (48, 232, 112)),
        }

    if palette_name == "cyberpunk":
        return {
            "idle": ((0, 210, 255), (140, 0, 255)),
            "session_start": ((0, 255, 220), (0, 90, 255)),
            "thinking": ((0, 232, 255), (120, 28, 255)),
            "tool_command": ((255, 24, 148), (255, 170, 0)),
            "tool_edit": ((56, 255, 128), (0, 210, 255)),
            "tool_read": ((0, 180, 255), (120, 80, 255)),
            "tool_agent": ((255, 42, 224), (0, 240, 255)),
            "error": ((255, 16, 48), (120, 0, 24)),
            "attention": ((255, 230, 0), (255, 24, 112)),
            "complete": ((64, 255, 110), (0, 245, 255)),
        }

    # Default: "omarchy-theme" — live-derived from Omarchy's active colors.toml
    c = read_omarchy_theme_colors()
    accent = boost_saturation(hex_to_rgb(c["accent"]), 0.35)
    red = boost_saturation(hex_to_rgb(c.get("bright_red", c["red"])), 0.45)
    orange = boost_saturation(hex_to_rgb(c.get("orange", c["yellow"])), 0.45)
    yellow = boost_saturation(hex_to_rgb(c.get("bright_yellow", c["yellow"])), 0.40)
    green = boost_saturation(hex_to_rgb(c.get("bright_green", c["green"])), 0.40)
    cyan = boost_saturation(hex_to_rgb(c.get("bright_cyan", c["cyan"])), 0.35)
    blue = boost_saturation(hex_to_rgb(c.get("bright_blue", c["blue"])), 0.35)
    magenta = boost_saturation(hex_to_rgb(c.get("bright_magenta", c["magenta"])), 0.45)

    return {
        "idle": (accent, scale_rgb(accent, 0.35)),
        "session_start": (cyan, accent),
        "thinking": (magenta, accent),
        "tool_command": (orange, yellow),
        "tool_edit": (green, cyan),
        "tool_read": (blue, cyan),
        "tool_agent": (magenta, yellow),
        "error": (red, scale_rgb(red, 0.25)),
        "attention": (yellow, red),
        "complete": (green, yellow),
    }


def get_swatches() -> List[Dict[str, str]]:
    """Curated swatch list combining active Omarchy theme colors + vivid RGB presets."""
    c = read_omarchy_theme_colors()
    swatches: List[Dict[str, str]] = [
        {"label": "Theme Accent", "hex": c["accent"], "group": "theme"},
        {"label": "Theme Red", "hex": c["red"], "group": "theme"},
        {"label": "Theme Orange", "hex": c["orange"], "group": "theme"},
        {"label": "Theme Yellow", "hex": c["yellow"], "group": "theme"},
        {"label": "Theme Green", "hex": c["green"], "group": "theme"},
        {"label": "Theme Cyan", "hex": c["cyan"], "group": "theme"},
        {"label": "Theme Blue", "hex": c["blue"], "group": "theme"},
        {"label": "Theme Magenta", "hex": c["magenta"], "group": "theme"},
        {"label": "Razer Green", "hex": "#44d62c", "group": "vivid"},
        {"label": "Hellfire", "hex": "#ff4500", "group": "vivid"},
        {"label": "Arcane", "hex": "#9b4dff", "group": "vivid"},
        {"label": "Crimson", "hex": "#ff1744", "group": "vivid"},
        {"label": "Gold", "hex": "#ffc400", "group": "vivid"},
        {"label": "Ice", "hex": "#00e5ff", "group": "vivid"},
        {"label": "Sakura", "hex": "#ff4da6", "group": "vivid"},
        {"label": "Pure White", "hex": "#ffffff", "group": "vivid"},
    ]
    return swatches
