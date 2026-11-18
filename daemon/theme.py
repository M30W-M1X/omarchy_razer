"""Omarchy theme reader and Adaptive Lighting color palette resolver."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

RGB = Tuple[int, int, int]

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
TOML_KV_RE = re.compile(r'^\s*([a-zA-Z0-9_]+)\s*=\s*"([^"]+)"')

PALETTES: Tuple[Tuple[str, str], ...] = (
    ("omarchy-theme", "Omarchy"),
    ("ember", "Ember"),
    ("cyberpunk", "Neon"),
    ("tokyo-night", "Tokyo"),
    ("synthwave", "Synthwave"),
    ("aurora", "Aurora"),
    ("matrix", "Matrix"),
    ("sakura", "Sakura"),
    ("arctic", "Arctic"),
    ("solar", "Solar"),
)

VALID_PALETTES: Tuple[str, ...] = tuple(k for k, _ in PALETTES)


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


STATIC_PALETTES: Dict[str, Dict[str, Tuple[RGB, RGB]]] = {
    "ember": {
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
    },
    "cyberpunk": {
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
    },
    "tokyo-night": {
        "idle": ((122, 162, 247), (65, 72, 104)),
        "session_start": ((125, 207, 255), (122, 162, 247)),
        "thinking": ((187, 154, 247), (122, 162, 247)),
        "tool_command": ((255, 158, 100), (224, 175, 104)),
        "tool_edit": ((115, 218, 202), (158, 206, 106)),
        "tool_read": ((42, 195, 222), (122, 162, 247)),
        "tool_agent": ((187, 154, 247), (115, 218, 202)),
        "error": ((247, 118, 142), (140, 24, 52)),
        "attention": ((224, 175, 104), (247, 118, 142)),
        "complete": ((158, 206, 106), (125, 207, 255)),
    },
    "synthwave": {
        "idle": ((255, 42, 164), (82, 18, 168)),
        "session_start": ((0, 240, 255), (255, 42, 164)),
        "thinking": ((255, 46, 190), (88, 24, 255)),
        "tool_command": ((255, 108, 28), (255, 42, 148)),
        "tool_edit": ((0, 245, 255), (255, 84, 210)),
        "tool_read": ((110, 66, 255), (0, 225, 255)),
        "tool_agent": ((255, 208, 48), (255, 36, 178)),
        "error": ((255, 18, 64), (110, 0, 48)),
        "attention": ((255, 214, 36), (255, 36, 132)),
        "complete": ((0, 255, 210), (255, 210, 64)),
    },
    "aurora": {
        "idle": ((32, 232, 178), (24, 92, 148)),
        "session_start": ((72, 255, 214), (48, 130, 255)),
        "thinking": ((42, 240, 172), (118, 64, 255)),
        "tool_command": ((148, 82, 255), (42, 235, 195)),
        "tool_edit": ((64, 255, 148), (48, 200, 255)),
        "tool_read": ((48, 195, 255), (28, 92, 210)),
        "tool_agent": ((164, 92, 255), (56, 255, 186)),
        "error": ((255, 62, 88), (110, 14, 48)),
        "attention": ((255, 196, 72), (164, 82, 255)),
        "complete": ((84, 255, 172), (120, 235, 255)),
    },
    "matrix": {
        "idle": ((0, 200, 64), (0, 56, 18)),
        "session_start": ((68, 255, 112), (0, 110, 32)),
        "thinking": ((32, 255, 88), (0, 84, 26)),
        "tool_command": ((148, 255, 48), (0, 196, 56)),
        "tool_edit": ((180, 255, 196), (0, 224, 72)),
        "tool_read": ((0, 232, 128), (0, 72, 36)),
        "tool_agent": ((96, 255, 72), (190, 255, 210)),
        "error": ((255, 24, 36), (92, 0, 8)),
        "attention": ((220, 255, 48), (0, 180, 48)),
        "complete": ((190, 255, 200), (32, 255, 92)),
    },
    "sakura": {
        "idle": ((255, 138, 190), (140, 56, 110)),
        "session_start": ((255, 184, 216), (255, 96, 168)),
        "thinking": ((255, 112, 186), (176, 86, 240)),
        "tool_command": ((255, 126, 98), (255, 196, 138)),
        "tool_edit": ((255, 190, 218), (132, 236, 182)),
        "tool_read": ((196, 132, 255), (255, 148, 204)),
        "tool_agent": ((255, 142, 208), (255, 214, 128)),
        "error": ((255, 36, 78), (128, 12, 42)),
        "attention": ((255, 204, 112), (255, 72, 136)),
        "complete": ((156, 248, 196), (255, 168, 210)),
    },
    "arctic": {
        "idle": ((140, 226, 255), (36, 98, 168)),
        "session_start": ((210, 246, 255), (64, 178, 255)),
        "thinking": ((110, 220, 255), (42, 108, 245)),
        "tool_command": ((210, 242, 255), (56, 172, 255)),
        "tool_edit": ((128, 255, 240), (72, 156, 255)),
        "tool_read": ((64, 164, 255), (24, 62, 168)),
        "tool_agent": ((190, 228, 255), (128, 142, 255)),
        "error": ((255, 44, 68), (96, 12, 32)),
        "attention": ((255, 220, 110), (92, 192, 255)),
        "complete": ((225, 252, 255), (96, 242, 218)),
    },
    "solar": {
        "idle": ((255, 168, 24), (136, 48, 6)),
        "session_start": ((255, 228, 96), (255, 116, 16)),
        "thinking": ((255, 186, 32), (210, 68, 12)),
        "tool_command": ((255, 96, 12), (255, 232, 92)),
        "tool_edit": ((255, 234, 104), (255, 142, 24)),
        "tool_read": ((255, 152, 48), (168, 56, 16)),
        "tool_agent": ((255, 242, 140), (255, 86, 18)),
        "error": ((255, 18, 18), (120, 4, 4)),
        "attention": ((255, 244, 96), (255, 48, 12)),
        "complete": ((255, 246, 156), (255, 178, 36)),
    },
}


def get_palette(palette_name: str) -> Dict[str, Tuple[RGB, RGB]]:
    """Return mapping of AI activity state -> (primary_rgb, secondary_rgb)."""
    if palette_name == "diablo":
        palette_name = "ember"
    if palette_name in STATIC_PALETTES:
        return STATIC_PALETTES[palette_name]

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


def get_palette_list() -> List[Dict[str, str]]:
    return [{"value": k, "label": label} for k, label in PALETTES]


def get_swatches() -> List[Dict[str, str]]:
    """Curated swatch list combining active Omarchy theme colors + vivid RGB presets."""
    c = read_omarchy_theme_colors()
    return [
        {"label": "Theme Accent", "hex": c["accent"], "group": "theme"},
        {"label": "Theme Red", "hex": c["red"], "group": "theme"},
        {"label": "Theme Orange", "hex": c["orange"], "group": "theme"},
        {"label": "Theme Yellow", "hex": c["yellow"], "group": "theme"},
        {"label": "Theme Green", "hex": c["green"], "group": "theme"},
        {"label": "Theme Cyan", "hex": c["cyan"], "group": "theme"},
        {"label": "Theme Blue", "hex": c["blue"], "group": "theme"},
        {"label": "Theme Magenta", "hex": c["magenta"], "group": "theme"},
        {"label": "Razer Green", "hex": "#44d62c", "group": "vivid"},
        {"label": "Ember", "hex": "#ff4500", "group": "vivid"},
        {"label": "Arcane", "hex": "#9b4dff", "group": "vivid"},
        {"label": "Crimson", "hex": "#ff1744", "group": "vivid"},
        {"label": "Gold", "hex": "#ffc400", "group": "vivid"},
        {"label": "Ice", "hex": "#00e5ff", "group": "vivid"},
        {"label": "Sakura", "hex": "#ff4da6", "group": "vivid"},
        {"label": "Pure White", "hex": "#ffffff", "group": "vivid"},
    ]
