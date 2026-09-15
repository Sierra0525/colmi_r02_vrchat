"""Diagnostic: list all BLE GATT services/characteristics the ring exposes.

Usage:
    py -3.13 scripts/list_services.py --address XX:XX:XX:XX:XX:XX

Looks in particular for the standard Bluetooth Heart Rate Service
(0000180d-0000-1000-8000-00805f9b34fb) and its Heart Rate Measurement
characteristic (00002a37-...). If present, we may be able to subscribe to
notifications directly via the standard GATT spec instead of the ring's
undocumented custom protocol.
"""

from __future__ import annotations

import argparse
import asyncio

from bleak import BleakClient

STANDARD_HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
STANDARD_HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"


async def main(address: str) -> None:
    async with BleakClient(address) as client:
        print(f"Connected to {address}\n")
        found_standard_hr = False
        for service in client.services:
            marker = " <-- standard Heart Rate Service!" if service.uuid.lower() == STANDARD_HR_SERVICE else ""
            print(f"Service {service.uuid} ({service.description}){marker}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                char_marker = " <-- standard Heart Rate Measurement!" if char.uuid.lower() == STANDARD_HR_MEASUREMENT else ""
                print(f"  Characteristic {char.uuid} [{props}] ({char.description}){char_marker}")
                if char.uuid.lower() == STANDARD_HR_MEASUREMENT:
                    found_standard_hr = True
            print()

        if found_standard_hr:
            print("=> This ring DOES expose the standard Heart Rate Service. We can likely use that directly.")
        else:
            print("=> No standard Heart Rate Service found. Stuck with the custom protocol.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.address))
