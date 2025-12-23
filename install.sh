#!/bin/bash
# Install script for Super Activity View Daemon v1.1.0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/super-activity-view"
SERVICE_FILE="/etc/systemd/system/super-activity-view.service"

echo "======================================"
echo "Super Activity View Daemon Installer"
echo "Version 1.1.0"
echo "======================================"

# Check for root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Install Python dependencies if not present
echo ""
echo "Checking dependencies..."
DEPS_TO_INSTALL=""

if ! python3 -c "import evdev" 2>/dev/null; then
    DEPS_TO_INSTALL="$DEPS_TO_INSTALL python3-evdev"
fi

if ! python3 -c "import pyudev" 2>/dev/null; then
    DEPS_TO_INSTALL="$DEPS_TO_INSTALL python3-pyudev"
fi

if [ -n "$DEPS_TO_INSTALL" ]; then
    echo "Installing dependencies:$DEPS_TO_INSTALL"
    apt-get update
    apt-get install -y $DEPS_TO_INSTALL
else
    echo "All Python dependencies are installed"
fi

# Create installation directory
echo ""
echo "Installing daemon..."
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/super_activity_daemon.py" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/super_activity_daemon.py"

# Install configuration GUI
echo "Installing configuration GUI..."
cp "$SCRIPT_DIR/super-activity-config.py" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/super-activity-config.py"

# Create symlink for easy command access
ln -sf "$INSTALL_DIR/super-activity-config.py" /usr/local/bin/super-activity-config

# Install desktop entry
echo "Installing desktop entry..."
cp "$SCRIPT_DIR/super-activity-config.desktop" "/usr/share/applications/"

# Install polkit rule for password-free service control
echo "Installing polkit rule..."
cp "$SCRIPT_DIR/50-super-activity-view.rules" "/etc/polkit-1/rules.d/"
chmod 644 "/etc/polkit-1/rules.d/50-super-activity-view.rules"

# Install sleep/wake hook
echo "Installing sleep/wake hook..."
cp "$SCRIPT_DIR/super-activity-view-sleep.sh" "/usr/lib/systemd/system-sleep/super-activity-view"
chmod +x "/usr/lib/systemd/system-sleep/super-activity-view"

# Install systemd service
echo "Installing systemd service..."
cp "$SCRIPT_DIR/super-activity-view.service" "$SERVICE_FILE"

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable and start service
echo "Enabling service..."
systemctl enable super-activity-view.service

echo "Starting service..."
systemctl restart super-activity-view.service

echo ""
echo "======================================"
echo "Installation complete!"
echo "======================================"
echo ""
echo "The daemon is now running. Single tap SUPER to open Activity View."
echo ""
echo "Configuration GUI:"
echo "  Search for 'Super Activity View Config' in your app menu"
echo "  Or run: super-activity-config"
echo ""
echo "Useful commands:"
echo "  Check status:  systemctl status super-activity-view"
echo "  View logs:     journalctl -u super-activity-view -f"
echo "  Restart:       systemctl restart super-activity-view"
echo "  Uninstall:     sudo ./uninstall.sh"
echo ""
echo "Note: Service control (start/stop/restart) works without password."
echo "Settings are saved to ~/.config/super-activity-view/config.json"
