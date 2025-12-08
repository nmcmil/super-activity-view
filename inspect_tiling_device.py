import evdev
for path in evdev.list_devices():
    d = evdev.InputDevice(path)
    if "Tiling" in d.name:
        print(f"Name: {d.name}")
        print(f"Path: {d.path}")
        print(f"Bus: {d.info.bustype} (Hex: {hex(d.info.bustype)})")
        print(f"Vendor: {hex(d.info.vendor)}")
        print(f"Product: {hex(d.info.product)}")
