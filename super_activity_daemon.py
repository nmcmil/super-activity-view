#!/usr/bin/env python3
"""
Super Key Activity View Daemon

Detects single SUPER key taps and opens GNOME Activity View via custom injection.
Ignores SUPER+key combinations AND SUPER+scroll/click.
Ignores Virtual Devices and known Proxy Devices to prevent conflicts.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

try:
    import evdev
    from evdev import ecodes, UInput
except ImportError:
    print("Error: evdev module not found. Install with: pip install evdev")
    sys.exit(1)

CONFIG_PATH = "/etc/super-activity-view/config.json"

# Key name to evdev code mapping
KEY_MAP = {
    "KEY_LEFTMETA": ecodes.KEY_LEFTMETA,
    "KEY_RIGHTMETA": ecodes.KEY_RIGHTMETA,
    "KEY_LEFTCTRL": ecodes.KEY_LEFTCTRL,
    "KEY_RIGHTCTRL": ecodes.KEY_RIGHTCTRL,
}


class SuperActivityDaemon:
    """Daemon that monitors SUPER key, other keys, and mouse actions."""
    
    # Maximum time (seconds) between press and release to be considered a "tap"
    TAP_TIMEOUT = 0.5
    
    def __init__(self):
        self.super_pressed = False
        self.super_press_time = 0
        self.other_key_pressed = False
        self.devices = []
        self.ui = None
        
        # Load configuration
        self.load_config()
        
        # Initialize Virtual Input Device
        try:
            self.ui = UInput(name="Super Activity Daemon")
            print("Virtual UInput device created successfully")
        except Exception as e:
            print(f"Failed to create UInput device: {e}")
            print("Make sure you are running as root or have access to /dev/uinput")
    
    def load_config(self):
        """Load configuration from file."""
        # Default configuration
        trigger_key = "KEY_LEFTMETA"
        injection_key = "KEY_LEFTCTRL"
        
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    trigger_key = config.get("trigger_key", trigger_key)
                    injection_key = config.get("injection_key", injection_key)
                    print(f"Loaded config: trigger={trigger_key}, injection={injection_key}")
        except (PermissionError, json.JSONDecodeError) as e:
            print(f"Could not load config, using defaults: {e}")
        
        # Convert key names to evdev codes
        self.SUPER_KEYS = {KEY_MAP.get(trigger_key, ecodes.KEY_LEFTMETA)}
        self.TRIGGER_KEYS = [KEY_MAP.get(injection_key, ecodes.KEY_LEFTCTRL)]
        
        print(f"Listening for: {trigger_key}")
        print(f"Will inject: {injection_key}")
        
        
    def find_input_devices(self):
        """Find keyboards and mice (filtering out virtual devices)."""
        input_devices = []
        for path in evdev.list_devices():
            try:
                device = evdev.InputDevice(path)
                name = device.name
                
                # FILTER: Ignore our own device
                if name == "Super Activity Daemon":
                    continue

                # FILTER: Ignore Tiling Shell Proxy (Masquerades as USB)
                if "Tiling Shell Proxy Device" in name:
                    # print(f"Ignoring Tiling Proxy: {name}")
                    continue
                
                # FILTER: Ignore BUS_VIRTUAL (0x06)
                if device.info.bustype == 0x06:
                    # print(f"Ignoring virtual device: {name}")
                    continue
                    
                caps = device.capabilities()
                
                # Check for Keyboard-like
                is_keyboard = False
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    if ecodes.KEY_A in keys and ecodes.KEY_SPACE in keys:
                        is_keyboard = True
                
                # Check for Mouse-like
                is_mouse = False
                if ecodes.EV_REL in caps:
                     is_mouse = True
                
                if is_keyboard or is_mouse:
                    input_devices.append(device)
                    dtype = "Keyboard" if is_keyboard else "Mouse/Other"
                    if is_keyboard and is_mouse: dtype = "Combo"
                    print(f"Found {dtype}: {name} ({device.path})")
                    
            except (PermissionError, OSError):
                pass
        return input_devices
    
    async def trigger_activity_view(self):
        """Trigger GNOME Activity View."""
        if not self.ui:
            return

        print("Triggering Activity View (Injecting logical Super)...")
        try:
            for key in self.TRIGGER_KEYS:
                self.ui.write(ecodes.EV_KEY, key, 1)
            self.ui.syn()
            await asyncio.sleep(0.05)
            for key in reversed(self.TRIGGER_KEYS):
                self.ui.write(ecodes.EV_KEY, key, 0)
            self.ui.syn()
        except OSError as e:
            print(f"Failed to inject keys: {e}")
    
    async def handle_event(self, event):
        """Handle a single input event."""
        
        # 1. Handle Key Events
        if event.type == ecodes.EV_KEY:
            key_code = event.code
            key_state = event.value  # 0=release, 1=press, 2=repeat
            
            # Handle SUPER key events
            if key_code in self.SUPER_KEYS:
                if key_state == 1:  # Press
                    self.super_pressed = True
                    self.super_press_time = time.time()
                    self.other_key_pressed = False
                    print(f"SUPER pressed ({ecodes.KEY.get(key_code)}) - tracking started")
                    
                elif key_state == 0:  # Release
                    if self.super_pressed:
                        elapsed = time.time() - self.super_press_time
                        
                        if not self.other_key_pressed and elapsed < self.TAP_TIMEOUT:
                            print(f"Clean SUPER tap detected ({elapsed:.3f}s)")
                            await self.trigger_activity_view()
                        else:
                            cause = "other action" if self.other_key_pressed else "held too long"
                            print(f"SUPER release ignored ({cause})")
                        
                        self.super_pressed = False
                        self.other_key_pressed = False
                        
            # Handle OTHER keys while SUPER is held
            elif self.super_pressed:
                if key_state == 1: # On Press
                    key_name = ecodes.KEY.get(key_code) or ecodes.BTN.get(key_code) or f"CODE_{key_code}"
                    print(f"Interaction detected (Key/Btn): {key_name} - Activity View negated")
                    self.other_key_pressed = True

        # 2. Handle Relative Events (Mouse Scroll)
        elif event.type == ecodes.EV_REL and self.super_pressed:
            if event.code in [ecodes.REL_WHEEL, ecodes.REL_HWHEEL]:
                if event.value != 0:
                    print("Interaction detected (Scroll) - Activity View negated")
                    self.other_key_pressed = True
    
    async def monitor_device(self, device):
        """Monitor a single device for events."""
        try:
            async for event in device.async_read_loop():
                await self.handle_event(event)
        except OSError as e:
            print(f"Device {device.name} disconnected: {e}")
    
    async def run(self):
        """Main run loop."""
        print("Super Activity View Daemon starting (Filtered Proxy Devices)...")
        self.devices = self.find_input_devices()
        
        if not self.devices:
            print("No input devices found!")
            sys.exit(1)
        
        tasks = [self.monitor_device(device) for device in self.devices]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            print("Shutting down...")
        finally:
            if self.ui:
                self.ui.close()
            for device in self.devices:
                try:
                    device.close()
                except:
                    pass

def main():
    daemon = SuperActivityDaemon()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        pass
    except PermissionError:
        print("Permission denied. Run with sudo.")
        sys.exit(1)

if __name__ == "__main__":
    main()
