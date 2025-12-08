import evdev
from evdev import ecodes
import sys

print("Finding keyboards...")
devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
keyboards = []
for dev in devices:
    if ecodes.EV_KEY in dev.capabilities():
        print(f"Checking {dev.name} ({dev.path})...")
        keyboards.append(dev)

if not keyboards:
    print("No keyboards found (run with sudo?)")
    sys.exit(1)

print(f"\nMonitoring {len(keyboards)} devices. Press your SUPER key now (Ctrl+C to stop)...")

for device in keyboards:
    try:
        device.grab() # Optional: grab to ensure we see it, but might block system
        device.ungrab()
    except:
        pass

# Simple blocking read from all devices
import select
devices_map = {dev.fd: dev for dev in keyboards}

try:
    while True:
        r, w, x = select.select(devices_map, [], [])
        for fd in r:
            dev = devices_map[fd]
            for event in dev.read():
                if event.type == ecodes.EV_KEY:
                    key_name = ecodes.KEY.get(event.code, "UNKNOWN")
                    # Only print press/release (skip repeat=2)
                    if event.value != 2:
                        state = "PRESSED" if event.value == 1 else "RELEASED"
                        print(f"Device: {dev.name} | Key: {key_name} ({event.code}) | State: {state}")
except KeyboardInterrupt:
    print("\nStopping...")
