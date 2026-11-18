#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DEST="$HOME/.config/omarchy/plugins/razer-chroma"
CLI_DEST="$HOME/.local/bin/omarchy-razer"
SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_DEST="$SYSTEMD_DIR/omarchy-razer-chroma.service"
SHELL_JSON="$HOME/.config/omarchy/shell.json"
AGY_HOOKS_JSON="$HOME/.gemini/config/hooks.json"

echo "==> Setting executable permissions..."
chmod +x \
  "$REPO_DIR/daemon/razer_chroma_daemon.py" \
  "$REPO_DIR/cli/omarchy-razer" \
  "$REPO_DIR/hooks/agy-razer-hook.py" \
  "$REPO_DIR/hooks/omarchy-theme-set.sh" \
  "$REPO_DIR/omarchy-plugin/helper.py" \
  "$REPO_DIR/install.sh"

echo "==> Linking Omarchy shell plugin -> $PLUGIN_DEST"
mkdir -p "$(dirname "$PLUGIN_DEST")"
ln -sfn "$REPO_DIR/omarchy-plugin" "$PLUGIN_DEST"

echo "==> Linking CLI -> $CLI_DEST"
mkdir -p "$(dirname "$CLI_DEST")"
ln -sfn "$REPO_DIR/cli/omarchy-razer" "$CLI_DEST"

echo "==> Installing systemd user service -> $SERVICE_DEST"
mkdir -p "$SYSTEMD_DIR"
cat > "$SERVICE_DEST" <<EOF
[Unit]
Description=Omarchy Razer Chroma & AI Reactive Lighting Daemon
Wants=openrazer-daemon.service
After=openrazer-daemon.service graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $REPO_DIR/daemon/razer_chroma_daemon.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now omarchy-razer-chroma.service || true

echo "==> Installing Omarchy theme-set hook..."
if command -v omarchy >/dev/null 2>&1; then
  omarchy hook install theme-set "$REPO_DIR/hooks/omarchy-theme-set.sh" || true
else
  mkdir -p "$HOME/.config/omarchy/hooks/theme-set.d"
  cp "$REPO_DIR/hooks/omarchy-theme-set.sh" "$HOME/.config/omarchy/hooks/theme-set.d/omarchy-theme-set.sh"
  chmod +x "$HOME/.config/omarchy/hooks/theme-set.d/omarchy-theme-set.sh"
fi

echo "==> Registering AGY lifecycle hooks in $AGY_HOOKS_JSON..."
python3 - "$AGY_HOOKS_JSON" "$REPO_DIR/hooks/agy-razer-hook.py" <<'PY'
import json, sys
from pathlib import Path

hooks_path = Path(sys.argv[1])
hook_script = sys.argv[2]
hooks_path.parent.mkdir(parents=True, exist_ok=True)

data = {}
if hooks_path.is_file():
    try:
        loaded = json.loads(hooks_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = {}

cmd = f"python3 '{hook_script}'"
handler = {"type": "command", "command": cmd, "timeout": 3}

data["razer-chroma"] = {
    "enabled": True,
    "SessionStart": [handler],
    "PreInvocation": [handler],
    "PostToolUse": [
        {
            "matcher": "*",
            "hooks": [handler],
        }
    ],
    "PostInvocation": [handler],
    "Stop": [handler],
}

tmp = hooks_path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
tmp.replace(hooks_path)
PY

echo "==> Adding razer.chroma widget to $SHELL_JSON (if not present)..."
if [ -f "$SHELL_JSON" ]; then
  python3 - "$SHELL_JSON" <<'PY'
import json, shutil, sys, time
from pathlib import Path

path = Path(sys.argv[1])
cfg = json.loads(path.read_text(encoding="utf-8"))
layout = cfg.setdefault("bar", {}).setdefault("layout", {})
sections = ("left", "centerBegin", "center", "centerEnd", "right", "tray")

exists = any(
    isinstance(item, dict) and item.get("id") == "razer.chroma"
    for sec in sections
    for item in layout.get(sec, [])
)

if not exists:
    backup = path.with_name(f"shell.json.bak.{int(time.time())}")
    shutil.copy2(path, backup)
    right = layout.setdefault("right", [])
    insert_at = len(right)
    for idx, item in enumerate(right):
        if isinstance(item, dict) and item.get("id") in ("wizard.panel", "omarchy.agents"):
            insert_at = idx + 1
            break
    right.insert(insert_at, {"id": "razer.chroma"})
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    print(f"Added razer.chroma to bar.layout.right (backup: {backup.name})")
else:
    print("razer.chroma is already configured in shell.json")
PY
fi

if command -v omarchy-shell >/dev/null 2>&1; then
  omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
fi

echo "==> Done! Omarchy Razer Chroma is installed."
