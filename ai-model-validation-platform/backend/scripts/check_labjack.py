#!/usr/bin/env python3
"""
Simple LabJack T-Series connection tester.
Works with T7 / T4 / T8 via USB or Ethernet.

Usage:
    python scripts/check_labjack.py
"""

from labjack import ljm


def main() -> None:
    print("🔍 Checking LJM installation...")

    try:
        # Open any T-series device via any connection (USB/Ethernet)
        handle = ljm.openS("ANY", "ANY", "ANY")
        print("✅ LJM library loaded successfully.")
    except Exception as exc:
        print("❌ Failed to load LJM or open device.")
        print("Error:", exc)
        return

    print("\n🔌 Checking device info...")
    try:
        device_type, connection_type, serial, ip, port, max_bytes = ljm.getHandleInfo(handle)
        print(f"   ▸ Device Type:      {device_type}")
        print(f"   ▸ Connection Type:  {connection_type}")
        print(f"   ▸ Serial Number:    {serial}")
        print(f"   ▸ IP Address:       {ip}")
        print("✅ Device opened successfully.")
    except Exception as exc:
        print("❌ Could not obtain device info.")
        print("Error:", exc)
        ljm.close(handle)
        return

    print("\n📡 Reading AIN0...")
    try:
        value = ljm.eReadName(handle, "AIN0")
        print(f"   ▸ AIN0 value: {value:.6f} V")
        print("✅ AIN0 read successful.")
    except Exception as exc:
        print("❌ Failed to read AIN0.")
        print("Error:", exc)
    finally:
        ljm.close(handle)
        print("\n🔚 Closed device. Test complete.\n")


if __name__ == "__main__":
    main()
