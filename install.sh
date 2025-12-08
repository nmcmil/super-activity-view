#!/bin/bash
# Install script for Super Activity View Daemon

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/super-activity-view"
CONFIG_DIR="/etc/super-activity-view"
SERVICE_FILE="/etc/systemd/system/super-activity-view.service"

echo "=================================="
echo "Super Activity View Daemon Installer"
echo "=================================="

# Check for root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Install Python evdev if not present
echo ""
echo "Checking dependencies..."
if ! python3 -c "import evdev" 2>/dev/null; then
    echo "Installing python3-evdev..."
    apt-get update
    apt-get install -y python3-evdev
else
    echo "python3-evdev is already installed"
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

# Install desktop entry
echo "Installing desktop entry..."
cp "$SCRIPT_DIR/super-activity-config.desktop" "/usr/share/applications/"

# Create default configuration
echo "Creating default configuration..."
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    cat > "$CONFIG_DIR/config.json" << 'CONFIGEOF'
{
  "trigger_key": "KEY_LEFTMETA",
  "injection_key": "KEY_LEFTCTRL"
}
CONFIGEOF
fi

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
echo "=================================="
echo "Installation complete!"
echo "=================================="
echo ""
echo "The daemon is now running. Single tap SUPER to open Activity View."
echo ""
echo "Configuration GUI:"
echo "  Search for 'Super Activity View Config' in your app menu"
echo "  Or run: python3 $INSTALL_DIR/super-activity-config.py"
echo ""
echo "Useful commands:"
echo "  Check status:  sudo systemctl status super-activity-view"
echo "  View logs:     sudo journalctl -u super-activity-view -f"
echo "  Stop service:  sudo systemctl stop super-activity-view"
echo "  Uninstall:     sudo ./uninstall.sh"

