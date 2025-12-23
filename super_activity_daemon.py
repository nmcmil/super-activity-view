#!/usr/bin/env python3
"""
Super Key Activity View Daemon

Detects single SUPER key taps and opens GNOME Activity View via custom injection.
Ignores SUPER+key combinations AND SUPER+scroll/click.
Ignores Virtual Devices and known Proxy Devices to prevent conflicts.
Supports dynamic device hotplug - automatically detects new keyboards/mice.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Unbuffered output for systemd journal
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

try:
    import evdev
    from evdev import ecodes, UInput
except ImportError:
    print("Error: evdev module not found. Install with: pip install evdev")
    sys.exit(1)

try:
    import pyudev
    HAVE_PYUDEV = True
except ImportError:
    HAVE_PYUDEV = False
    print("Warning: pyudev not found. Device hotplug detection disabled.")
    print("Install with: pip install pyudev")

# Config paths - check user config first, then system config
# When running as root (systemd), we need to find the actual user's config
def get_user_config_paths():
    """Get possible user config paths, handling root execution."""
    paths = []
    
    # If running as normal user
    user_path = os.path.expanduser("~/.config/super-activity-view/config.json")
    if not user_path.startswith("/root"):
        paths.append(user_path)
    
    # Check SUDO_USER environment variable
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        paths.append(f"/home/{sudo_user}/.config/super-activity-view/config.json")
    
    # Check all users in /home/ (for systemd service running as root)
    try:
        for user_dir in os.listdir("/home"):
            user_config = f"/home/{user_dir}/.config/super-activity-view/config.json"
            if user_config not in paths:
                paths.append(user_config)
    except (PermissionError, FileNotFoundError):
        pass
    
    return paths

SYSTEM_CONFIG_PATH = "/etc/super-activity-view/config.json"

# Key name to evdev code mapping
KEY_MAP = {
    "KEY_LEFTMETA": ecodes.KEY_LEFTMETA,
    "KEY_RIGHTMETA": ecodes.KEY_RIGHTMETA,
    "KEY_LEFTCTRL": ecodes.KEY_LEFTCTRL,
    "KEY_RIGHTCTRL": ecodes.KEY_RIGHTCTRL,
}


class SuperActivityDaemon:
    """Daemon that monitors SUPER key, other keys, and mouse actions."""
    
    # Default maximum time (seconds) between press and release to be considered a "tap"
    DEFAULT_TAP_TIMEOUT = 0.5
    
    # How often to rescan for new devices (seconds) - fallback if pyudev unavailable
    DEVICE_SCAN_INTERVAL = 5.0
    
    def __init__(self):
        self.super_pressed = False
        self.super_press_time = 0
        self.other_key_pressed = False
        self.devices = {}  # path -> device
        self.device_tasks = {}  # path -> task
        self.ui = None
        self.tap_timeout = self.DEFAULT_TAP_TIMEOUT
        self.running = False
        
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
        """Load configuration from file (user config takes priority)."""
        # Default configuration
        trigger_key = "KEY_LEFTMETA"
        injection_key = "KEY_LEFTCTRL"
        
        # Determine which config file to use (user config takes priority)
        config_path = None
        # Check user configs first, then system config
        search_paths = get_user_config_paths() + [SYSTEM_CONFIG_PATH]
        for path in search_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if config_path:
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    trigger_key = config.get("trigger_key", trigger_key)
                    injection_key = config.get("injection_key", injection_key)
                    self.tap_timeout = config.get("tap_timeout", self.DEFAULT_TAP_TIMEOUT)
                    print(f"Loaded config from {config_path}")
                    print(f"  trigger={trigger_key}, injection={injection_key}, tap_timeout={self.tap_timeout}s")
            except (PermissionError, json.JSONDecodeError) as e:
                print(f"Could not load config from {config_path}: {e}")
        else:
            print("No config file found, using defaults")
        
        # Convert key names to evdev codes
        self.SUPER_KEYS = {KEY_MAP.get(trigger_key, ecodes.KEY_LEFTMETA)}
        self.TRIGGER_KEYS = [KEY_MAP.get(injection_key, ecodes.KEY_LEFTCTRL)]
        
        print(f"Listening for: {trigger_key}")
        print(f"Will inject: {injection_key}")
        print(f"Tap timeout: {self.tap_timeout}s")
    
    def is_valid_device(self, device):
        """Check if a device should be monitored."""
        try:
            name = device.name
            
            # FILTER: Ignore our own device
            if name == "Super Activity Daemon":
                return False

            # FILTER: Ignore Tiling Shell Proxy (Masquerades as USB)
            if "Tiling Shell Proxy Device" in name:
                return False
            
            # FILTER: Ignore BUS_VIRTUAL (0x06)
            if device.info.bustype == 0x06:
                return False
                
            caps = device.capabilities()
            
            # Check for Keyboard-like
            is_keyboard = False
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                if ecodes.KEY_A in keys and ecodes.KEY_SPACE in keys:
                    is_keyboard = True
            
            # Check for Mouse-like
            is_mouse = ecodes.EV_REL in caps
            
            return is_keyboard or is_mouse
        except (PermissionError, OSError):
            return False
    
    def get_device_type(self, device):
        """Get a human-readable device type."""
        try:
            caps = device.capabilities()
            is_keyboard = ecodes.EV_KEY in caps and ecodes.KEY_A in caps.get(ecodes.EV_KEY, [])
            is_mouse = ecodes.EV_REL in caps
            if is_keyboard and is_mouse:
                return "Combo"
            elif is_keyboard:
                return "Keyboard"
            else:
                return "Mouse/Other"
        except:
            return "Unknown"
        
    def find_input_devices(self):
        """Find keyboards and mice (filtering out virtual devices)."""
        input_devices = {}
        for path in evdev.list_devices():
            try:
                device = evdev.InputDevice(path)
                if self.is_valid_device(device):
                    input_devices[path] = device
                    dtype = self.get_device_type(device)
                    print(f"Found {dtype}: {device.name} ({device.path})")
                else:
                    device.close()
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
                        
                        if not self.other_key_pressed and elapsed < self.tap_timeout:
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
        path = device.path
        try:
            async for event in device.async_read_loop():
                await self.handle_event(event)
        except OSError as e:
            print(f"Device disconnected: {device.name} ({path})")
        finally:
            # Clean up disconnected device
            if path in self.devices:
                del self.devices[path]
            if path in self.device_tasks:
                del self.device_tasks[path]
            try:
                device.close()
            except:
                pass
    
    def add_device(self, path):
        """Add a new device to monitoring."""
        if path in self.devices:
            return  # Already monitoring
        
        try:
            device = evdev.InputDevice(path)
            if self.is_valid_device(device):
                self.devices[path] = device
                task = asyncio.create_task(self.monitor_device(device))
                self.device_tasks[path] = task
                dtype = self.get_device_type(device)
                print(f"Hotplug: Added {dtype}: {device.name} ({path})")
            else:
                device.close()
        except (PermissionError, OSError, FileNotFoundError):
            pass
    
    def remove_device(self, path):
        """Remove a device from monitoring."""
        if path in self.device_tasks:
            self.device_tasks[path].cancel()
            del self.device_tasks[path]
        if path in self.devices:
            try:
                self.devices[path].close()
            except:
                pass
            del self.devices[path]
            print(f"Hotplug: Removed device at {path}")
    
    async def watch_devices_pyudev(self):
        """Watch for device changes using pyudev."""
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='input')
        
        # Make the monitor non-blocking
        monitor.start()
        
        print("Device hotplug monitoring enabled (pyudev)")
        
        loop = asyncio.get_event_loop()
        
        while self.running:
            # Run blocking poll in executor to not block the event loop
            device = await loop.run_in_executor(None, lambda: monitor.poll(timeout=1.0))
            if device is None:
                continue
                
            # Only care about event devices
            if device.device_node and device.device_node.startswith('/dev/input/event'):
                if device.action == 'add':
                    # Small delay to let device initialize
                    await asyncio.sleep(0.5)
                    self.add_device(device.device_node)
                elif device.action == 'remove':
                    self.remove_device(device.device_node)
    
    async def watch_devices_poll(self):
        """Fallback: periodically scan for new devices."""
        print(f"Device hotplug monitoring enabled (polling every {self.DEVICE_SCAN_INTERVAL}s)")
        
        while self.running:
            await asyncio.sleep(self.DEVICE_SCAN_INTERVAL)
            
            # Find current devices
            current_paths = set(evdev.list_devices())
            monitored_paths = set(self.devices.keys())
            
            # Add new devices
            for path in current_paths - monitored_paths:
                self.add_device(path)
            
            # Remove stale devices (handled by monitor_device when they disconnect)
    
    async def run(self):
        """Main run loop with dynamic device management."""
        print("Super Activity View Daemon starting (with hotplug support)...")
        self.running = True
        
        # Find initial devices
        self.devices = self.find_input_devices()
        
        if not self.devices:
            print("No input devices found! Will wait for devices to be connected...")
        
        # Start monitoring existing devices
        for path, device in self.devices.items():
            task = asyncio.create_task(self.monitor_device(device))
            self.device_tasks[path] = task
        
        # Start device hotplug watcher
        if HAVE_PYUDEV:
            hotplug_task = asyncio.create_task(self.watch_devices_pyudev())
        else:
            hotplug_task = asyncio.create_task(self.watch_devices_poll())
        
        try:
            # Keep running until cancelled
            while self.running:
                await asyncio.sleep(1)
                
                # If we have no devices, keep waiting
                if not self.devices:
                    continue
        except asyncio.CancelledError:
            print("Shutting down...")
        finally:
            self.running = False
            hotplug_task.cancel()
            
            # Cancel all device tasks
            for task in self.device_tasks.values():
                task.cancel()
            
            # Close all devices
            if self.ui:
                self.ui.close()
            for device in self.devices.values():
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
