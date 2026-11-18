"""Unit & regression tests for Omarchy Razer Chroma."""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from daemon.animations import render_matrix_frame, render_mouse_color
from daemon.razer_chroma_daemon import RazerChromaDaemon, STATE_PRIORITY
from daemon.theme import VALID_PALETTES, get_palette, get_swatches, hex_to_rgb, read_omarchy_theme_colors, rgb_to_hex


def _load_agy_hook():
    spec = importlib.util.spec_from_file_location("agy_razer_hook", REPO_ROOT / "hooks/agy-razer-hook.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestThemeAndPalettes(unittest.TestCase):
    def test_hex_roundtrip(self) -> None:
        self.assertEqual(hex_to_rgb("#7fbbb3"), (127, 187, 179))
        self.assertEqual(rgb_to_hex((127, 187, 179)), "#7fbbb3")
        self.assertEqual(hex_to_rgb("invalid", (1, 2, 3)), (1, 2, 3))

    def test_all_palettes_have_all_states(self) -> None:
        self.assertGreaterEqual(len(VALID_PALETTES), 10)
        for pal_name in VALID_PALETTES:
            pal = get_palette(pal_name)
            for state in STATE_PRIORITY:
                self.assertIn(state, pal, f"{pal_name} missing {state}")
                p, s = pal[state]
                self.assertEqual(len(p), 3)
                self.assertEqual(len(s), 3)

    def test_theme_and_swatches(self) -> None:
        colors = read_omarchy_theme_colors()
        self.assertIn("accent", colors)
        swatches = get_swatches()
        self.assertGreaterEqual(len(swatches), 16)


class TestAnimations(unittest.TestCase):
    def test_matrix_frames_huntsman_and_lancehead(self) -> None:
        for dims in ((5, 15), (1, 16)):
            rows, cols = dims
            for state in STATE_PRIORITY:
                frame = render_matrix_frame(state, rows, cols, 0.75, (255, 80, 20), (120, 20, 255))
                self.assertEqual(len(frame), rows)
                self.assertEqual(len(frame[0]), cols)
                for r in frame:
                    for rgb in r:
                        self.assertEqual(len(rgb), 3)
                        for ch in rgb:
                            self.assertGreaterEqual(ch, 0)
                            self.assertLessEqual(ch, 255)

    def test_mouse_color_all_states(self) -> None:
        for state in STATE_PRIORITY:
            c = render_mouse_color(state, 0.5, (200, 100, 50), (50, 100, 200))
            self.assertEqual(len(c), 3)
            for ch in c:
                self.assertGreaterEqual(ch, 0)
                self.assertLessEqual(ch, 255)


class TestAgyHookMapping(unittest.TestCase):
    def test_event_mappings(self) -> None:
        hook = _load_agy_hook()
        self.assertEqual(hook.map_agy_event({"hookEventName": "SessionStart"})[0], "session_start")
        self.assertEqual(hook.map_agy_event({"hookEventName": "PreInvocation"})[0], "thinking")
        self.assertEqual(
            hook.map_agy_event({"hookEventName": "PostToolUse", "toolCall": {"name": "run_command"}})[0],
            "tool_command",
        )
        self.assertEqual(
            hook.map_agy_event({"hookEventName": "PostToolUse", "toolCall": {"name": "edit_file"}})[0],
            "tool_edit",
        )
        self.assertEqual(
            hook.map_agy_event({"hookEventName": "PostToolUse", "toolCall": {"name": "read_file"}})[0],
            "tool_read",
        )
        self.assertEqual(
            hook.map_agy_event({"hookEventName": "PostToolUse", "toolCall": {"name": "invoke_subagent"}})[0],
            "tool_agent",
        )
        self.assertEqual(
            hook.map_agy_event({"hookEventName": "PostToolUse", "toolCall": {"name": "run_command"}, "error": "exit 1"})[0],
            "error",
        )
        self.assertEqual(
            hook.map_agy_event({"hookEventName": "Stop", "terminationReason": "NO_TOOL_CALL"})[0],
            "complete",
        )
        self.assertEqual(
            hook.map_agy_event({"hookEventName": "Stop", "terminationReason": "ERROR"})[0],
            "error",
        )
        self.assertEqual(
            hook.map_agy_event({"hookEventName": "Stop", "terminationReason": "USER_CANCELED"})[0],
            "attention",
        )


class TestDaemonStateMachine(unittest.TestCase):
    def test_priority_arbitration_and_commands(self) -> None:
        d = RazerChromaDaemon()
        # Prevent disk writes in unit test
        d._save_config = lambda: None  # type: ignore[method-assign]
        d._apply_idle_lighting = lambda: None  # type: ignore[method-assign]

        d.handle_command({"cmd": "ai_event", "session": "s1", "state": "thinking", "source": "agy"})
        d.handle_command({"cmd": "ai_event", "session": "s2", "state": "tool_command", "source": "agy"})
        snap = d.snapshot()
        self.assertEqual(snap["ai"]["state"], "tool_command")
        self.assertEqual(snap["ai"]["sessionCount"], 2)

        d.handle_command({"cmd": "ai_event", "session": "s2", "state": "idle"})
        snap = d.snapshot()
        self.assertEqual(snap["ai"]["state"], "thinking")

        d.handle_command({"cmd": "set_palette", "palette": "ember"})
        self.assertEqual(d.config["palette"], "ember")

        d.handle_command({"cmd": "set_color", "color": "#44d62c", "target": "mouse"})
        self.assertEqual(d.config["mouseColor"], "#44d62c")


class TestPluginUiSafety(unittest.TestCase):
    def test_all_qml_text_elements_use_plain_text(self) -> None:
        qml = (REPO_ROOT / "omarchy-plugin/Panel.qml").read_text(encoding="utf-8")
        self.assertIn("function sanitizePlainText", qml)
        self.assertIn("sanitizePlainText(base)", qml)

        blocks = []
        for match in re.finditer(r"(?<![A-Za-z0-9_])Text\s*\{", qml):
            depth = 1
            pos = match.end()
            while pos < len(qml) and depth > 0:
                if qml[pos] == "{":
                    depth += 1
                elif qml[pos] == "}":
                    depth -= 1
                pos += 1
            blocks.append(qml[match.end() : pos - 1])

        self.assertGreater(len(blocks), 5)
        for idx, body in enumerate(blocks):
            self.assertIn(
                "textFormat: Text.PlainText",
                body,
                f"Text block #{idx} in Panel.qml is missing textFormat: Text.PlainText",
            )


if __name__ == "__main__":
    unittest.main()
