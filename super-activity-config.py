#!/usr/bin/env python3
"""
Super Activity View Configuration GUI

A GTK4/libadwaita application for configuring the super-activity-view daemon.
Allows users to select which key triggers Activity View and which key to inject.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
import json
import os
import subprocess
import sys

CONFIG_PATH = os.path.expanduser("~/.config/super-activity-view/config.json")
SERVICE_NAME = "super-activity-view.service"

# Key options for trigger and injection
KEY_OPTIONS = {
    "Super (Left)": "KEY_LEFTMETA",
    "Super (Right)": "KEY_RIGHTMETA",
    "Ctrl (Left)": "KEY_LEFTCTRL",
    "Ctrl (Right)": "KEY_RIGHTCTRL",
}

class SuperActivityConfig(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.super-activity-config",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.config = {
            "trigger_key": "KEY_LEFTMETA",
            "injection_key": "KEY_LEFTCTRL",
            "tap_timeout": 0.5
        }
        self._save_timeout_id = None  # For debouncing saves
        self.load_config()
        
        # Register actions for toast buttons
        restart_action = Gio.SimpleAction.new("restart-service", None)
        restart_action.connect("activate", self.on_restart_action)
        self.add_action(restart_action)
        
    def load_config(self):
        """Load configuration from file."""
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    self.config.update(json.load(f))
        except (PermissionError, json.JSONDecodeError) as e:
            print(f"Could not load config: {e}")
    
    def save_config(self):
        """Save configuration to user config file."""
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False
    
    def get_service_status(self):
        """Get the current service status."""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', SERVICE_NAME],
                capture_output=True, text=True
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False
    
    def control_service(self, action):
        """Start, stop, or restart the service."""
        try:
            # Use systemctl directly - polkit rule handles authorization
            subprocess.run(
                ['systemctl', action, SERVICE_NAME],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def do_activate(self):
        """Create and show the main window."""
        win = Adw.ApplicationWindow(application=self)
        win.set_title("Super Activity View Configuration")
        win.set_default_size(450, 400)
        
        # Toast overlay for notifications (doesn't affect window size)
        self.toast_overlay = Adw.ToastOverlay()
        win.set_content(self.toast_overlay)
        
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(main_box)
        
        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)
        
        # Content with clamp for proper sizing
        clamp = Adw.Clamp()
        clamp.set_maximum_size(600)
        clamp.set_margin_top(20)
        clamp.set_margin_bottom(20)
        clamp.set_margin_start(20)
        clamp.set_margin_end(20)
        main_box.append(clamp)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        clamp.set_child(content_box)
        
        # === Trigger Key Group ===
        trigger_group = Adw.PreferencesGroup()
        trigger_group.set_title("Trigger Key")
        trigger_group.set_description("Which physical key opens Activity View when tapped")
        content_box.append(trigger_group)
        
        # Trigger key dropdown
        trigger_row = Adw.ComboRow()
        trigger_row.set_title("Listen for")
        
        trigger_model = Gtk.StringList()
        key_names = list(KEY_OPTIONS.keys())
        selected_trigger_idx = 0
        current_trigger = self.config.get("trigger_key", "KEY_LEFTMETA")
        for i, name in enumerate(key_names):
            trigger_model.append(name)
            if KEY_OPTIONS[name] == current_trigger:
                selected_trigger_idx = i
        
        trigger_row.set_model(trigger_model)
        trigger_row.set_selected(selected_trigger_idx)
        trigger_row.connect("notify::selected", self.on_trigger_changed, key_names)
        trigger_group.add(trigger_row)
        
        # === Injection Key Group ===
        injection_group = Adw.PreferencesGroup()
        injection_group.set_title("Injection Key")
        injection_group.set_description("Which key is sent to trigger the Overview (must match system shortcut)")
        content_box.append(injection_group)
        
        # Injection key dropdown
        injection_row = Adw.ComboRow()
        injection_row.set_title("Inject")
        
        injection_model = Gtk.StringList()
        selected_injection_idx = 0
        current_injection = self.config.get("injection_key", "KEY_LEFTCTRL")
        for i, name in enumerate(key_names):
            injection_model.append(name)
            if KEY_OPTIONS[name] == current_injection:
                selected_injection_idx = i
        
        injection_row.set_model(injection_model)
        injection_row.set_selected(selected_injection_idx)
        injection_row.connect("notify::selected", self.on_injection_changed, key_names)
        injection_group.add(injection_row)
        
        # === Timing Group ===
        timing_group = Adw.PreferencesGroup()
        timing_group.set_title("Timing")
        timing_group.set_description("Adjust how quickly you must tap the key")
        content_box.append(timing_group)
        
        # Tap timeout spin row
        timeout_row = Adw.SpinRow.new_with_range(0.05, 2.0, 0.05)
        timeout_row.set_title("Tap Timeout")
        timeout_row.set_subtitle("Max time between press and release (seconds)")
        timeout_row.set_digits(2)
        timeout_row.set_value(self.config.get("tap_timeout", 0.5))
        timeout_row.connect("notify::value", self.on_timeout_changed)
        timing_group.add(timeout_row)
        
        # Track if restart is needed
        self.needs_restart = False
        
        # === Service Control Group ===
        service_group = Adw.PreferencesGroup()
        service_group.set_title("Service Control")
        content_box.append(service_group)
        
        # Status row
        self.status_row = Adw.ActionRow()
        self.status_row.set_title("Service Status")
        self.update_status_display()
        service_group.add(self.status_row)

        # Launch at startup switch
        startup_row = Adw.SwitchRow()
        startup_row.set_title("Launch at Startup")
        startup_row.set_subtitle("Automatically start service on boot")
        startup_row.set_active(self.get_service_enabled_status())
        startup_row.connect("notify::active", self.on_startup_toggled)
        service_group.add(startup_row)
        
        # Control buttons row
        control_row = Adw.ActionRow()
        control_row.set_title("Controls")
        
        control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        control_box.set_valign(Gtk.Align.CENTER)
        
        start_btn = Gtk.Button(label="Start")
        start_btn.connect("clicked", lambda b: self.on_service_action("start"))
        control_box.append(start_btn)
        
        stop_btn = Gtk.Button(label="Stop")
        stop_btn.connect("clicked", lambda b: self.on_service_action("stop"))
        control_box.append(stop_btn)
        
        restart_btn = Gtk.Button(label="Restart")
        restart_btn.connect("clicked", lambda b: self.on_service_action("restart"))
        control_box.append(restart_btn)
        
        control_row.add_suffix(control_box)
        service_group.add(control_row)
        
        win.present()
    
    def on_trigger_changed(self, row, param, key_names):
        """Handle trigger key selection change."""
        idx = row.get_selected()
        if idx < len(key_names):
            new_key = KEY_OPTIONS[key_names[idx]]
            if new_key != self.config.get("trigger_key"):
                self.config["trigger_key"] = new_key
                self.show_restart_toast()
                self.save_config()
    
    def on_injection_changed(self, row, param, key_names):
        """Handle injection key selection change."""
        idx = row.get_selected()
        if idx < len(key_names):
            new_key = KEY_OPTIONS[key_names[idx]]
            if new_key != self.config.get("injection_key"):
                self.config["injection_key"] = new_key
                self.show_restart_toast()
                self.save_config()
    
    def on_timeout_changed(self, row, param):
        """Handle tap timeout value change (debounced)."""
        new_value = round(row.get_value(), 2)
        if new_value != self.config.get("tap_timeout"):
            self.config["tap_timeout"] = new_value
            self.needs_restart = True
            
            # Cancel any pending save
            if self._save_timeout_id:
                GLib.source_remove(self._save_timeout_id)
            
            # Debounce: save after 500ms of no changes
            self._save_timeout_id = GLib.timeout_add(500, self._debounced_save)
    
    def _debounced_save(self):
        """Actually save config after debounce delay."""
        self._save_timeout_id = None
        self.save_config()
        if self.needs_restart:
            self.show_restart_toast()
        return False  # Don't repeat
    
    def show_restart_toast(self):
        """Show a toast notification that restart is required (only once)."""
        # Don't show duplicate toasts
        if hasattr(self, '_restart_toast_shown') and self._restart_toast_shown:
            return
        
        self._restart_toast_shown = True
        self.needs_restart = True
        toast = Adw.Toast(title="Restart required to apply changes")
        toast.set_button_label("Restart Now")
        toast.set_action_name("app.restart-service")
        toast.set_timeout(5)
        # Reset flag when toast is dismissed
        toast.connect("dismissed", lambda t: setattr(self, '_restart_toast_shown', False))
        self.toast_overlay.add_toast(toast)
    
    def on_restart_action(self, action, param):
        """Handle restart action from toast button."""
        self.on_service_action("restart")
    
    def on_service_action(self, action):
        """Handle service control button click."""
        if self.control_service(action):
            GLib.timeout_add(500, self.update_status_display)
            if action == "restart":
                self.needs_restart = False
                # Show success toast
                toast = Adw.Toast(title="Service restarted successfully")
                toast.set_timeout(2)
                self.toast_overlay.add_toast(toast)
        else:
            self.show_message("Error", f"Failed to {action} service")
    
    def update_status_display(self):
        """Update the service status display."""
        is_active = self.get_service_status()
        status_text = "Running" if is_active else "Stopped"
        
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.set_label(status_text)
            if is_active:
                self.status_label.remove_css_class("error")
                self.status_label.add_css_class("success")
            else:
                self.status_label.remove_css_class("success")
                self.status_label.add_css_class("error")
        else:
            self.status_label = Gtk.Label(label=status_text)
            self.status_label.add_css_class("success" if is_active else "error")
            self.status_row.add_suffix(self.status_label)
        
        return False
    
    def get_service_enabled_status(self):
        """Check if the service is enabled."""
        try:
            result = subprocess.run(
                ['systemctl', 'is-enabled', SERVICE_NAME],
                capture_output=True, text=True
            )
            return result.stdout.strip() == "enabled"
        except Exception:
            return False

    def on_startup_toggled(self, row, param):
        """Handle launch at startup toggle."""
        is_enabled = row.get_active()
        action = "enable" if is_enabled else "disable"
        
        try:
            # enable/disable requires pkexec (not covered by our polkit rule)
            subprocess.run(
                ['pkexec', 'systemctl', action, SERVICE_NAME],
                check=True
            )
        except subprocess.CalledProcessError:
            # Revert switch if failed
            row.set_active(not is_enabled)
            self.show_message("Error", f"Failed to {action} startup service")
    
    def show_message(self, title, message):
        """Show a message dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self.get_active_window(),
            heading=title,
            body=message
        )
        dialog.add_response("ok", "OK")
        dialog.present()


def main():
    app = SuperActivityConfig()
    return app.run(sys.argv)


if __name__ == "__main__":
    main()
