#!/bin/bash
# Omarchy theme-set hook: notify Razer Chroma daemon to reload theme colors.
set -euo pipefail

if command -v omarchy-razer >/dev/null 2>&1; then
  omarchy-razer reload-theme >/dev/null 2>&1 || true
elif [ -x "$HOME/.local/bin/omarchy-razer" ]; then
  "$HOME/.local/bin/omarchy-razer" reload-theme >/dev/null 2>&1 || true
fi
