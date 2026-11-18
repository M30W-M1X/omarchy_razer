"""Diablo 4-inspired procedural per-key RGB matrix and mouse animations."""

from __future__ import annotations

import math
from typing import List, Tuple

from .theme import RGB, blend, scale_rgb

MatrixFrame = List[List[RGB]]


def _hash01(a: int, b: int, step: int) -> float:
    """Deterministic pseudo-random float in [0, 1) without global RNG state."""
    x = (a * 374761393 + b * 668265263 + step * 1442695041) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFF) / 0x1000000


def render_matrix_frame(
    state: str,
    rows: int,
    cols: int,
    elapsed: float,
    primary: RGB,
    secondary: RGB,
) -> MatrixFrame:
    """Render one procedural RGB frame for a (rows x cols) Razer key matrix."""
    rows = max(1, rows)
    cols = max(1, cols)
    frame: MatrixFrame = [[(0, 0, 0) for _ in range(cols)] for _ in range(rows)]

    cx = (cols - 1) / 2.0
    cy = (rows - 1) / 2.0
    max_dist = math.hypot(cx, cy) or 1.0

    if state == "session_start":
        # Portal ignition: sweeping beam from left to right with warm afterglow
        progress = min(1.35, elapsed * 1.4)
        beam_x = progress * cols
        for r in range(rows):
            for c in range(cols):
                d = c - beam_x
                if d < 0:
                    tail = math.exp(d * 0.35)
                    frame[r][c] = blend(scale_rgb(secondary, 0.35), primary, tail)
                else:
                    lead = math.exp(-d * 1.8)
                    frame[r][c] = scale_rgb(primary, lead * 0.9)
        return frame

    if state == "thinking":
        # Arcane channeling: smooth sweeping wave back and forth + shimmering mana bed
        pos = (math.sin(elapsed * 2.4) * 0.5 + 0.5) * (cols - 1)
        bed = scale_rgb(secondary, 0.22)
        for r in range(rows):
            row_phase = math.sin(elapsed * 3.1 + r * 0.65) * 0.5 + 0.5
            for c in range(cols):
                dist = abs(c - pos)
                beam = math.exp(-(dist * dist) / max(2.2, (cols * 0.17) ** 2))
                shimmer = 0.15 * (math.sin(elapsed * 4.5 + c * 0.55 - r * 0.7) * 0.5 + 0.5)
                color = blend(bed, primary, min(1.0, beam * 0.95 + shimmer * row_phase))
                frame[r][c] = color
        return frame

    if state == "tool_command":
        # Hellfire forge: fiery rising embers from bottom row to top row
        step = int(elapsed * 14.0)
        frac = (elapsed * 14.0) - step
        hot_core = blend(secondary, (255, 245, 200), 0.45)
        for r in range(rows):
            # y=0 at bottom row, y=1 at top row
            y = (rows - 1 - r) / max(1, rows - 1)
            for c in range(cols):
                n0 = _hash01(c, r + step, 17)
                n1 = _hash01(c, r + step + 1, 17)
                flicker = n0 * (1.0 - frac) + n1 * frac
                wave = math.sin(elapsed * 6.5 + c * 0.8 + r * 0.4) * 0.15
                heat = max(0.0, min(1.0, (1.0 - y * 0.72) * (0.55 + 0.55 * flicker) + wave))
                if heat > 0.78:
                    frame[r][c] = blend(secondary, hot_core, (heat - 0.78) / 0.22)
                elif heat > 0.35:
                    frame[r][c] = blend(primary, secondary, (heat - 0.35) / 0.43)
                else:
                    frame[r][c] = scale_rgb(primary, max(0.08, heat / 0.35))
        return frame

    if state == "tool_edit":
        # Runeforging: crisp runner on number row + typing/crafting sparks across keys
        runner = (elapsed * cols * 1.15) % cols
        spark_tick = int(elapsed * 10.0)
        spark_frac = (elapsed * 10.0) - spark_tick
        bed = scale_rgb(secondary, 0.16)
        for r in range(rows):
            for c in range(cols):
                if r == 0:
                    d = min(abs(c - runner), cols - abs(c - runner))
                    bar = math.exp(-(d * d) / 2.6)
                    frame[r][c] = blend(scale_rgb(secondary, 0.28), primary, bar)
                else:
                    s_cur = _hash01(c, r, spark_tick)
                    s_prev = _hash01(c, r, spark_tick - 1)
                    val = 0.0
                    if s_cur > 0.89:
                        val = max(val, 1.0 - spark_frac * 0.55)
                    if s_prev > 0.89:
                        val = max(val, (1.0 - spark_frac) * 0.45)
                    pulse = 0.12 * (math.sin(elapsed * 4.0 + c * 0.4) * 0.5 + 0.5)
                    frame[r][c] = blend(bed, primary, min(1.0, val + pulse))
        return frame

    if state == "tool_read":
        # Arcane radar: dual crisp scanning columns sweeping across the matrix
        scan_a = (elapsed * cols * 0.85) % cols
        scan_b = (cols - 1) - ((elapsed * cols * 0.55) % cols)
        bed = scale_rgb(secondary, 0.14)
        for r in range(rows):
            for c in range(cols):
                da = abs(c - scan_a)
                db = abs(c - scan_b)
                ga = math.exp(-(da * da) / 1.8)
                gb = math.exp(-(db * db) / 2.2) * 0.65
                intensity = min(1.0, ga + gb)
                col_c = blend(secondary, primary, ga / max(0.01, ga + gb))
                frame[r][c] = blend(bed, col_c, intensity)
        return frame

    if state == "tool_agent":
        # Swarm conduit: 3 orbiting energy orbs lighting keys around them
        orbs = [
            (
                (math.sin(elapsed * 2.1) * 0.45 + 0.5) * (cols - 1),
                (math.cos(elapsed * 1.7) * 0.42 + 0.5) * (rows - 1),
                primary,
            ),
            (
                (math.cos(elapsed * 2.6 + 1.4) * 0.45 + 0.5) * (cols - 1),
                (math.sin(elapsed * 2.3 + 0.6) * 0.42 + 0.5) * (rows - 1),
                secondary,
            ),
            (
                (math.sin(elapsed * 1.6 + 3.1) * 0.45 + 0.5) * (cols - 1),
                (math.cos(elapsed * 2.9 + 2.0) * 0.42 + 0.5) * (rows - 1),
                blend(primary, secondary, 0.5),
            ),
        ]
        bed = scale_rgb(primary, 0.10)
        for r in range(rows):
            for c in range(cols):
                acc_r, acc_g, acc_b = float(bed[0]), float(bed[1]), float(bed[2])
                for ox, oy, oc in orbs:
                    d2 = (c - ox) ** 2 + ((r - oy) * 1.6) ** 2
                    glow = math.exp(-d2 / 5.5)
                    acc_r += oc[0] * glow
                    acc_g += oc[1] * glow
                    acc_b += oc[2] * glow
                frame[r][c] = (
                    min(255, int(acc_r)),
                    min(255, int(acc_g)),
                    min(255, int(acc_b)),
                )
        return frame

    if state == "error":
        # Diablo low-HP / damage taken: sharp crimson shockwave + double heartbeat pulse
        cycle = elapsed % 0.95
        if cycle < 0.16:
            beat = math.sin((cycle / 0.16) * math.pi)
        elif 0.24 < cycle < 0.42:
            beat = 0.85 * math.sin(((cycle - 0.24) / 0.18) * math.pi)
        else:
            beat = 0.12
        # Subtle outward vignette emphasis on edges like Diablo damage vignette
        for r in range(rows):
            for c in range(cols):
                edge = math.hypot(c - cx, (r - cy) * 1.6) / max_dist
                intensity = max(0.08, min(1.0, beat * (0.65 + 0.5 * edge)))
                frame[r][c] = blend(scale_rgb(secondary, 0.25), primary, intensity)
        return frame

    if state == "attention":
        # Sanctuary beacon: pulsing golden/amber ring from center outward
        ring = (elapsed * 1.6) % 1.25
        for r in range(rows):
            for c in range(cols):
                d = math.hypot(c - cx, (r - cy) * 1.6) / max_dist
                wave = math.exp(-((d - ring) ** 2) / 0.045)
                pulse = 0.2 + 0.25 * (math.sin(elapsed * 5.0) * 0.5 + 0.5)
                frame[r][c] = blend(scale_rgb(secondary, pulse), primary, wave)
        return frame

    if state == "complete":
        # Legendary loot drop: radial shockwave burst expanding outward + golden shimmer
        burst_r = elapsed * 1.75
        fade = max(0.0, 1.0 - max(0.0, elapsed - 1.6) / 1.4)
        spark_step = int(elapsed * 12.0)
        for r in range(rows):
            for c in range(cols):
                d = math.hypot(c - cx, (r - cy) * 1.5) / max_dist
                ring = math.exp(-((d - burst_r) ** 2) / 0.04)
                inside = 0.45 if d < burst_r else 0.08
                twinkle = 0.55 if _hash01(c, r, spark_step) > 0.85 else 0.0
                col = blend(primary, secondary, min(1.0, ring + twinkle * 0.7))
                level = min(1.0, (ring + inside + twinkle * 0.45)) * fade
                frame[r][c] = scale_rgb(col, level)
        return frame

    # Fallback gentle breathing
    breath = 0.45 + 0.55 * (math.sin(elapsed * 2.2) * 0.5 + 0.5)
    c_now = scale_rgb(primary, breath)
    for r in range(rows):
        for c in range(cols):
            frame[r][c] = c_now
    return frame


def render_mouse_color(
    state: str,
    elapsed: float,
    primary: RGB,
    secondary: RGB,
) -> RGB:
    """Compute smooth synced RGB color for mouse zones."""
    if state == "error":
        cycle = elapsed % 0.95
        if cycle < 0.16:
            beat = math.sin((cycle / 0.16) * math.pi)
        elif 0.24 < cycle < 0.42:
            beat = 0.85 * math.sin(((cycle - 0.24) / 0.18) * math.pi)
        else:
            beat = 0.15
        return blend(scale_rgb(secondary, 0.2), primary, beat)

    if state == "tool_command":
        flicker = 0.5 + 0.5 * math.sin(elapsed * 11.0) * math.cos(elapsed * 4.3)
        return blend(primary, secondary, flicker)

    if state == "complete":
        fade = max(0.0, 1.0 - max(0.0, elapsed - 1.6) / 1.4)
        pulse = 0.65 + 0.35 * math.sin(elapsed * 8.0)
        return scale_rgb(blend(primary, secondary, 0.5 + 0.5 * math.sin(elapsed * 6.0)), pulse * fade)

    if state == "attention":
        t = math.sin(elapsed * 6.0) * 0.5 + 0.5
        return blend(secondary, primary, t)

    if state in ("thinking", "tool_read", "tool_edit", "tool_agent", "session_start"):
        t = math.sin(elapsed * 3.2) * 0.5 + 0.5
        return blend(scale_rgb(secondary, 0.45), primary, t)

    return primary
