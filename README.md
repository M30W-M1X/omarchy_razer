# Omarchy Razer Chroma

An [Omarchy](https://omarchy.org/) shell bar plugin + background daemon that controls Razer Chroma keyboards and mice via [OpenRazer](https://openrazer.github.io/), synced live to your Omarchy theme and featuring **Diablo 4-style AI-reactive lighting** driven by Antigravity (AGY) lifecycle hooks.

## Features

- **Native Omarchy Top-Bar Plugin (`razer.chroma`)**:
  - Custom geometric Chroma icon with a live RGB indicator dot that mirrors your current hardware/AI color and pulses when an AI harness is active.
  - **Lighting Modes**: `Theme` (live Omarchy `colors.toml` / `keyboard.rgb` sync), `Static`, `Breath`, `Wave`, `Spectrum`, `Reactive`, `Starlight`, and `Off`.
  - **Color Picker**: One-click swatches for your active Omarchy theme + vivid RGB presets, custom `#RRGGBB` hex input, and per-target coloring (`All`, `Keyboard`, `Mouse`).
  - **Brightness Slider**: Native Omarchy `PanelSlider` (0–100%).
  - **Built-in Effect Previews**: Test `Think`, `Forge`, `Edit`, `Error`, and `Loot` animations straight from the bar popup.
- **Diablo 4-Style Per-Key AI Reactive Engine**:
  - Drives per-key RGB matrix animations on matrix-capable keyboards (e.g., Razer Huntsman Mini `5x15`) and multi-zone/matrix mice (e.g., Razer Lancehead Wireless `1x16`).
  - **3 Built-in Palettes**:
    - **Omarchy Theme (default)**: Automatically derives every AI activity state color from your active Omarchy theme's `colors.toml` and updates live when you switch themes!
    - **Diablo Sanctuary**: Arcane violet thinking sweeps, hellfire forge embers, molten gold runeforging, crimson blood-pulse damage flashes, and golden legendary loot bursts.
    - **Cyberpunk Neon**: Electric cyan, hot magenta, acid lime, and warning crimson.

### AI Activity → Lighting Map

| AGY Lifecycle Event | State | Animation |
|---|---|---|
| `SessionStart` | `session_start` | Left-to-right portal ignition sweep |
| `PreInvocation` | `thinking` | Smooth arcane channeling wave + shimmering bed |
| `PostToolUse` (`run_command`, etc.) | `tool_command` | Rising hellfire forge embers from bottom row to top |
| `PostToolUse` (`edit_file`, `write_file`) | `tool_edit` | Top-row progress runner + crafting sparks across keys |
| `PostToolUse` (`read_file`, `search_web`) | `tool_read` | Dual-edge arcane radar sweep |
| `PostToolUse` (`invoke_subagent`, `swarm`) | `tool_agent` | Orbiting swarm conduit energy orbs |
| `PostToolUse` / `Stop` (error) | `error` | Crimson shockwave + double heartbeat damage flash |
| `Stop` (`USER_CANCELED`, limit) | `attention` | Pulsing radial sanctuary beacon |
| `Stop` (`NO_TOOL_CALL`, done) | `complete` | Expanding radial legendary loot-drop burst → returns to idle |

## Prerequisites (Arch / Omarchy)

```bash
omarchy pkg add openrazer-driver-dkms openrazer-daemon python-openrazer
sudo gpasswd -a "$USER" openrazer
systemctl --user enable --now openrazer-daemon.service
```

> **Note:** After adding yourself to the `openrazer` group for the first time, log out and back in (or reboot) so your desktop session picks up the new group membership.

## Install

```bash
git clone https://github.com/M30W-M1X/omarchy_razer.git ~/Projects/omarchy_razer
cd ~/Projects/omarchy_razer
./install.sh
```

The installer:
1. Symlinks `omarchy-plugin/` into `~/.config/omarchy/plugins/razer-chroma`
2. Symlinks `cli/omarchy-razer` into `~/.local/bin/omarchy-razer`
3. Installs and starts `omarchy-razer-chroma.service` (systemd user unit)
4. Installs the Omarchy `theme-set` hook for instant theme sync
5. Registers the `"razer-chroma"` lifecycle hook in `~/.gemini/config/hooks.json` (preserving existing hooks)
6. Adds `razer.chroma` to `~/.config/omarchy/shell.json`

## CLI Usage

```bash
omarchy-razer status
omarchy-razer mode theme
omarchy-razer color "#ff4500" --target keyboard
omarchy-razer color "#9b4dff" --target mouse
omarchy-razer brightness 80
omarchy-razer palette diablo
omarchy-razer preview complete
omarchy-razer reactive on
```

## License

MIT
