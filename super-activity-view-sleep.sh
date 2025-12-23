#!/bin/bash
# Restart super-activity-view on resume from sleep
# This ensures device handles are refreshed after wake

case $1 in
    post)
        systemctl restart super-activity-view.service
        ;;
esac
