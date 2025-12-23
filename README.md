# Super Activity View

A lightweight daemon for Ubuntu/GNOME that enables **single-tap SUPER key** to open the Activity View, while preserving SUPER+key shortcuts.

## The Problem

By default in GNOME, the SUPER key opens Activity View. But if you use SUPER as a modifier for shortcuts (like a Mac-style Super+C for copy, Super+V for paste), the Activity View gets triggered every time you use a shortcut.

## The Solution

This daemon intercepts keyboard events at a low level using `evdev` and:

- **Single SUPER tap** → Opens Activity View
- **SUPER + any other key** → Does nothing (lets the shortcut work normally)
- **Long SUPER press** → Does nothing (configurable timeout)

## Features

- **Adjustable Tap Timeout**: Configure how quickly you must tap (0.05s - 2.0s)
- **Keyboard Support**: Tap trigger key → Activity View; Trigger + Key → Shortcut
- **Mouse Support**: Trigger + Click/Scroll/Drag → Shortcuts work normally
- **Key Swap Support**: Configurable trigger and injection keys via GUI
- **Device Hotplug**: Automatically detects new keyboards/mice without restart
- **Sleep/Wake Support**: Automatically recovers after system sleep
- **Password-Free Operation**: Service control without repeated authentication

## Requirements

- Ubuntu 22.04+ (or other Linux with GNOME/Python3)
- Python 3.8+
- `python3-evdev` package
- `python3-pyudev` package (for device hotplug)
- GTK4 and libadwaita (for configuration GUI)
- Access to input devices (root or `input` group membership)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/nmcmil/super-activity-view.git
cd super-activity-view
```

### 2. Install Dependencies

```bash
sudo apt install python3-evdev python3-pyudev python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

### 3. Run the Installer

```bash
sudo ./install.sh
```

This will:
- Install the daemon to `/opt/super-activity-view/`
- Set up the systemd service
- Install the configuration GUI desktop entry
- Install a polkit rule for password-free service control
- Install a sleep hook for automatic recovery after wake

### 4. Start the Service

```bash
systemctl restart super-activity-view.service
```

## Uninstallation

```bash
sudo ./uninstall.sh
```

## Configuration

After installation, search for **"Super Activity View Config"** in your app menu, or run:

```bash
super-activity-config
```

### Settings

| Setting | Description |
|---------|-------------|
| **Trigger Key** | Which physical key to listen for (Super or Ctrl, left/right) |
| **Injection Key** | Which key is sent to trigger the Overview |
| **Tap Timeout** | How quickly you must tap the key (0.05s - 2.0s) |
| **Launch at Startup** | Enable/disable automatic start on boot |

This is especially useful if you've **swapped your Super and Ctrl keys** using GNOME Tweaks.

### Configuration File

User settings are stored in `~/.config/super-activity-view/config.json`:

```json
{
  "trigger_key": "KEY_LEFTMETA",
  "injection_key": "KEY_LEFTCTRL",
  "tap_timeout": 0.15
}
```

## Manual Usage

For testing without installing as a service:

```bash
# Install dependencies
sudo apt install python3-evdev python3-pyudev

# Run daemon (requires root for input device access)
sudo python3 super_activity_daemon.py
```

## How It Works

1. **Monitors all keyboards and mice** using the Linux evdev interface
2. **Tracks trigger key state** - records when pressed and if other keys follow
3. **On trigger key release** - if no other keys were pressed and within timeout:
   - Injects the configured injection key via `uinput`
   - Opens Activity View

## Troubleshooting

### "No keyboards found"

Add your user to the `input` group:
```bash
sudo usermod -aG input $USER
# Then log out and back in
```

### Activity View doesn't open

1. Open the configuration GUI and try different key combinations
2. Adjust the Tap Timeout if it's too sensitive or not sensitive enough
3. Check logs:
```bash
journalctl -u super-activity-view -f
```

### Service not starting after reboot

```bash
sudo systemctl enable super-activity-view.service
sudo systemctl restart super-activity-view.service
```

### Device not detected after connecting

The daemon automatically detects new devices via hotplug. If a device isn't working:
```bash
systemctl restart super-activity-view.service
```

## Changelog

### v1.1.0 (2024-12-22)

**New Features:**
- **Adjustable Tap Timeout**: New slider in the GUI to configure how quickly you must tap the trigger key (0.05s - 2.0s). Lower values are more aggressive, higher values more lenient.
- **Device Hotplug Support**: Automatically detects when keyboards/mice are connected or disconnected without needing a service restart.
- **Sleep/Wake Recovery**: Service automatically restarts when your system wakes from sleep.

**Improvements:**
- **Password-Free Service Control**: Added a polkit rule (`/etc/polkit-1/rules.d/50-super-activity-view.rules`) that allows controlling the service without repeated password prompts. This rule only grants permission to start/stop/restart the super-activity-view service specifically.
- **User Config Location**: Settings now stored in `~/.config/super-activity-view/` instead of `/etc/`, eliminating the need for authentication when changing settings.
- **Toast Notifications**: Replaced inline "restart required" message with non-intrusive toast notifications.

### v1.0.0

- Initial release with GUI configuration
- Configurable trigger and injection keys
- Mouse scroll/click detection

## Security Notes

The polkit rule installed at `/etc/polkit-1/rules.d/50-super-activity-view.rules` allows active, local users to control the super-activity-view service without a password. This is scoped specifically to this service and does not grant broader systemd permissions. You can review or remove this file if you prefer to require a password for service control.

## License

MIT License - see LICENSE file
