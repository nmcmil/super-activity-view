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

CONFIG_PATH = "/etc/super-activity-view/config.json"
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
            "injection_key": "KEY_LEFTCTRL"
        }
        self.load_config()
        
    def load_config(self):
        """Load configuration from file."""
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    self.config.update(json.load(f))
        except (PermissionError, json.JSONDecodeError) as e:
            print(f"Could not load config: {e}")
    
    def save_config(self):
        """Save configuration to file (requires sudo)."""
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except PermissionError:
            try:
                config_json = json.dumps(self.config, indent=2)
                subprocess.run([
                    'pkexec', 'bash', '-c',
                    f'mkdir -p /etc/super-activity-view && echo \'{config_json}\' > {CONFIG_PATH}'
                ], check=True)
                return True
            except subprocess.CalledProcessError:
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
            subprocess.run(
                ['pkexec', 'systemctl', action, SERVICE_NAME],
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
        
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        win.set_content(main_box)
        
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
        
        # Restart notice (hidden by default)
        self.restart_notice = Adw.ActionRow()
        self.restart_notice.set_title("⚠️ Restart Required")
        self.restart_notice.set_subtitle("Click Restart below to apply changes")
        self.restart_notice.set_visible(False)
        injection_group.add(self.restart_notice)
        
        # === Service Control Group ===
        service_group = Adw.PreferencesGroup()
        service_group.set_title("Service Control")
        content_box.append(service_group)
        
        # Status row
        self.status_row = Adw.ActionRow()
        self.status_row.set_title("Service Status")
        self.update_status_display()
        service_group.add(self.status_row)
        
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
                self.restart_notice.set_visible(True)
                self.save_config()
    
    def on_injection_changed(self, row, param, key_names):
        """Handle injection key selection change."""
        idx = row.get_selected()
        if idx < len(key_names):
            new_key = KEY_OPTIONS[key_names[idx]]
            if new_key != self.config.get("injection_key"):
                self.config["injection_key"] = new_key
                self.restart_notice.set_visible(True)
                self.save_config()
    
    def on_service_action(self, action):
        """Handle service control button click."""
        if self.control_service(action):
            GLib.timeout_add(500, self.update_status_display)
            if action == "restart":
                self.restart_notice.set_visible(False)
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
