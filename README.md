# Omarchy Razer Chroma

An [Omarchy](https://omarchy.org/) shell bar plugin + background daemon that controls Razer Chroma keyboards and mice via [OpenRazer](https://openrazer.github.io/), synced live to your Omarchy theme and featuring **Adaptive Lighting** driven by Antigravity (AGY) lifecycle hooks.

## Features

- **Native Omarchy Top-Bar Plugin (`razer.chroma`)**:
  - Custom geometric Chroma icon with a live RGB indicator dot that mirrors your current hardware/AI color and pulses when an AI harness is active.
  - **Lighting Modes**: `Theme` (live Omarchy `colors.toml` / `keyboard.rgb` sync), `Static`, `Breath`, `Wave`, `Spectrum`, `Reactive`, `Starlight`, and `Off`.
  - **Color Picker**: One-click swatches for your active Omarchy theme + vivid RGB presets, custom `#RRGGBB` hex input, and per-target coloring (`All`, `Keyboard`, `Mouse`).
  - **Brightness Slider**: Native Omarchy `PanelSlider` (0–100%).
  - **Built-in Effect Previews**: Test `Think`, `Run`, `Edit`, `Error`, and `Done` animations straight from the bar popup.
- **Per-Key Adaptive Lighting Engine**:
  - Drives per-key RGB matrix animations on matrix-capable keyboards (e.g., Razer Huntsman Mini `5x15`) and multi-zone/matrix mice (e.g., Razer Lancehead Wireless `1x16`).
  - **3 Built-in Palettes**:
    - **Omarchy Theme (default)**: Automatically derives every Adaptive Lighting state color from your active Omarchy theme's `colors.toml` and updates live when you switch themes!
    - **Ember**: Deep violet thinking sweeps, rising ember orange for shell commands, warm gold for code edits, crimson alert pulses, and golden completion bursts.
    - **Cyberpunk Neon**: Electric cyan, hot magenta, acid lime, and warning crimson.

### AI Activity → Adaptive Lighting Map

| AGY Lifecycle Event | State | Animation |
|---|---|---|
| `SessionStart` | `session_start` | Left-to-right ignition sweep |
| `PreInvocation` | `thinking` | Smooth channeling wave + shimmering ambient bed |
| `PostToolUse` (`run_command`, etc.) | `tool_command` | Rising embers from bottom row to top |
| `PostToolUse` (`edit_file`, `write_file`) | `tool_edit` | Top-row progress runner + typing sparks across keys |
| `PostToolUse` (`read_file`, `search_web`) | `tool_read` | Dual-edge radar sweep |
| `PostToolUse` (`invoke_subagent`, `swarm`) | `tool_agent` | Orbiting multi-node energy orbs |
| `PostToolUse` / `Stop` (error) | `error` | Crimson shockwave + double-heartbeat alert pulse |
| `Stop` (`USER_CANCELED`, limit) | `attention` | Pulsing radial attention beacon |
| `Stop` (`NO_TOOL_CALL`, done) | `complete` | Expanding radial completion burst → returns to idle |

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
omarchy-razer palette ember
omarchy-razer preview complete
omarchy-razer reactive on
```

## License

MIT
