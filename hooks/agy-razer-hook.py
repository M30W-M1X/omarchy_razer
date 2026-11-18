#!/usr/bin/env python3
"""Antigravity (AGY) lifecycle hook for Omarchy Razer Chroma.

Maps AGY conversation lifecycle events into reactive Diablo-style lighting
events over the local Unix socket, then immediately emits `{}` on stdout so
AGY execution is never blocked or altered.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


def _socket_path() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/omarchy-razer-{os.getuid()}"))
    return runtime / "omarchy-razer-chroma.sock"


def _classify_tool(tool_name: str) -> str:
    name = (tool_name or "").strip().lower()
    if any(k in name for k in ("run_command", "command", "bash", "shell", "terminal", "exec", "manage_task")):
        return "tool_command"
    if any(k in name for k in ("edit", "write", "replace", "patch", "delete", "create")):
        return "tool_edit"
    if any(k in name for k in ("subagent", "swarm", "workflow", "send_message", "agent")):
        return "tool_agent"
    if any(k in name for k in ("ask_question", "confirm", "prompt")):
        return "attention"
    return "tool_read"


def map_agy_event(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return (razer_state, tool_name, detail) for an AGY hook payload."""
    event = str(payload.get("hookEventName") or "").strip()
    tool_call = payload.get("toolCall") if isinstance(payload.get("toolCall"), dict) else {}
    tool_name = str(tool_call.get("name") or "").strip()
    error_text = str(payload.get("error") or "").strip()

    if event == "SessionStart":
        return ("session_start", "", "AGY session started")

    if event == "PreInvocation":
        return ("thinking", "", "Thinking")

    if event == "PostToolUse":
        if error_text:
            return ("error", tool_name, f"{tool_name or 'tool'} failed")
        state = _classify_tool(tool_name)
        return (state, tool_name, tool_name or "Tool finished")

    if event == "PostInvocation":
        return ("thinking", "", "Processing")

    if event == "Stop":
        reason = str(payload.get("terminationReason") or "").strip().upper()
        if error_text or reason == "ERROR":
            return ("error", "", "Turn ended with error")
        if reason in ("USER_CANCELED", "MAX_INVOCATIONS", "MAX_FORCED_INVOCATIONS", "MAX_TOKEN_BUDGET_EXCEEDED"):
            return ("attention", "", reason.replace("_", " ").title())
        return ("complete", "", "Turn complete")

    return ("thinking", tool_name, event or "Active")


def _notify_daemon(session_id: str, state: str, tool: str, detail: str) -> None:
    spath = _socket_path()
    if not spath.exists():
        return
    req = {
        "cmd": "ai_event",
        "state": state,
        "session": session_id or "agy-default",
        "source": "agy",
        "tool": tool,
        "detail": detail,
    }
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            sock.connect(str(spath))
            sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
            sock.recv(1024)
    except Exception:
        pass


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if isinstance(payload, dict):
            session_id = str(payload.get("conversationId") or "agy-default")
            state, tool, detail = map_agy_event(payload)
            _notify_daemon(session_id, state, tool, detail)
    except Exception:
        pass
    finally:
        # Always emit a valid empty JSON object for AGY
        sys.stdout.write("{}\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
