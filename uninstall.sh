#!/bin/bash
# Uninstall script for Super Activity View Daemon

set -e

INSTALL_DIR="/opt/super-activity-view"
SERVICE_FILE="/etc/systemd/system/super-activity-view.service"

echo "======================================"
echo "Super Activity View Daemon Uninstaller"
echo "======================================"

# Check for root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Stop and disable service
echo "Stopping service..."
systemctl stop super-activity-view.service 2>/dev/null || true
systemctl disable super-activity-view.service 2>/dev/null || true

# Remove service file
echo "Removing systemd service..."
rm -f "$SERVICE_FILE"
systemctl daemon-reload

# Remove installation directory
echo "Removing installation files..."
rm -rf "$INSTALL_DIR"

# Remove symlink
echo "Removing command symlink..."
rm -f /usr/local/bin/super-activity-config

# Remove desktop entry
echo "Removing desktop entry..."
rm -f /usr/share/applications/super-activity-config.desktop

# Remove polkit rule
echo "Removing polkit rule..."
rm -f /etc/polkit-1/rules.d/50-super-activity-view.rules

# Remove sleep hook
echo "Removing sleep/wake hook..."
rm -f /usr/lib/systemd/system-sleep/super-activity-view

echo ""
echo "======================================"
echo "Uninstallation complete!"
echo "======================================"
echo ""
echo "The Super Activity View daemon has been removed."
echo ""
echo "Note: User config at ~/.config/super-activity-view/ was preserved."
echo "      Delete it manually if you want to remove all traces."
