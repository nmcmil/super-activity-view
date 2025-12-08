# Super Activity View Daemon

A lightweight daemon for Ubuntu/GNOME that enables **single-tap SUPER key** to open the Activity View, while preserving SUPER+key shortcuts.

## The Problem

By default in GNOME, the SUPER key opens Activity View. But if you use SUPER as a modifier for shortcuts (like a Mac-style Super+C for copy, Super+V for paste), the Activity View gets triggered every time you use a shortcut.

## The Solution

This daemon intercepts keyboard events at a low level using `evdev` and:

- **Single SUPER tap** → Opens Activity View
- **SUPER + any other key** → Does nothing (lets the shortcut work normally)
- **Long SUPER press** (> 0.5s) → Does nothing

## Requirements

- Ubuntu 20.04+ (or other Linux with GNOME/Python3)
- Python 3.8+
- `python3-evdev` package
- GTK4 and libadwaita (for configuration GUI)
- Access to input devices (root or `input` group membership)

## Quick Install

```bash
# Clone/download this repository
cd super-activity-view

# Install (requires sudo)
sudo ./install.sh
```

## Quick Uninstall

```bash
sudo ./uninstall.sh
```

## Configuration GUI

After installation, search for **"Super Activity View Config"** in your app menu, or run:

```bash
python3 /opt/super-activity-view/super-activity-config.py
```

The GUI lets you configure:
- **Trigger Key**: Which physical key to listen for (Super or Ctrl, left/right)
- **Injection Key**: Which key is sent to trigger the Overview
- **Service Controls**: Start/Stop/Restart the daemon

This is especially useful if you've **swapped your Super and Ctrl keys** using GNOME Tweaks.

### Configuration File

Settings are stored in `/etc/super-activity-view/config.json`:

```json
{
  "trigger_key": "KEY_LEFTMETA",
  "injection_key": "KEY_LEFTCTRL"
}
```

## Manual Usage

For testing without installing as a service:

```bash
# Install evdev
sudo apt install python3-evdev

# Run daemon (requires root for input device access)
sudo python3 super_activity_daemon.py
```

## How It Works

1. **Monitors all keyboards** using the Linux evdev interface
2. **Tracks trigger key state** - records when pressed and if other keys follow
3. **On trigger key release** - if no other keys were pressed and within timeout:
   - Injects the configured injection key via `uinput`
   - Opens Activity View

## Features

- **Keyboard Support**:
  - Tap trigger key → Activity View
  - Trigger + Key → Shortcut (e.g. Copy/Paste)
- **Mouse Support**:
  - Trigger + Click → Shortcut (Ignored)
  - Trigger + Scroll → Shortcut (e.g. Zoom in Figma)
  - Trigger + Drag → Shortcut (Ignored)
- **Key Swap Support**:
  - Configurable trigger and injection keys via GUI
  - Works with GNOME Tweaks "Swap Left Win and Left Ctrl"
- **Conflict Resolution**:
  - Ignores virtual devices (like Tiling Shell daemons) to prevent false triggers

## Troubleshooting

### "No keyboards found"

Add your user to the `input` group:
```bash
sudo usermod -aG input $USER
# Then log out and back in
```

### Activity View doesn't open

1. Open the configuration GUI and try different key combinations
2. Check logs:
```bash
sudo journalctl -u super-activity-view -f
```

### Service not starting after reboot

```bash
sudo systemctl enable super-activity-view.service
sudo systemctl restart super-activity-view.service
```

## License

MIT License - see LICENSE file
