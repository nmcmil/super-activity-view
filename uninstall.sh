#!/bin/bash
# Uninstall script for Super Activity View Daemon

set -e

INSTALL_DIR="/opt/super-activity-view"
SERVICE_FILE="/etc/systemd/system/super-activity-view.service"

echo "=================================="
echo "Super Activity View Daemon Uninstaller"
echo "=================================="

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

echo ""
echo "=================================="
echo "Uninstallation complete!"
echo "=================================="
echo ""
echo "The Super Activity View daemon has been removed."
echo "Note: python3-evdev was not removed (may be used by other programs)."
