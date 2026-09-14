"""CLI entry point: colmi-r02-vrchat"""

from __future__ import annotations

import argparse
import asyncio
import logging

from colmi_r02_vrchat.osc_bridge import VRChatOSC
from colmi_r02_vrchat.ring import Connected, Disconnected, HeartRate, NoReading, stream_heart_rate

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", required=True, help="Bluetooth address of the Colmi R02 ring (see colmi_r02_util scan)")
    parser.add_argument("--osc-ip", default="127.0.0.1", help="VRChat OSC listen address (default: 127.0.0.1)")
    parser.add_argument("--osc-port", type=int, default=9000, help="VRChat OSC listen port (default: 9000)")
    parser.add_argument("--reconnect-delay", type=float, default=5.0, help="Seconds to wait before reconnecting to the ring after a disconnect")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


NO_READING_LOG_EVERY = 5  # cycles (~seconds) between "still waiting" log lines


async def run(address: str, osc_ip: str, osc_port: int, reconnect_delay: float) -> None:
    osc = VRChatOSC(osc_ip, osc_port)
    no_reading_streak = 0

    async for event in stream_heart_rate(address, reconnect_delay=reconnect_delay):
        match event:
            case Connected():
                osc.send_connected(True)
                no_reading_streak = 0
            case Disconnected():
                osc.send_connected(False)
            case HeartRate(bpm=bpm):
                logger.info(f"Heart rate: {bpm} bpm")
                osc.send_heart_rate(bpm)
                no_reading_streak = 0
            case NoReading():
                no_reading_streak += 1
                if no_reading_streak == 1 or no_reading_streak % NO_READING_LOG_EVERY == 0:
                    logger.info("Waiting for a valid heart rate reading (is the ring worn snugly?)")
                else:
                    logger.debug("No valid reading this cycle")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(name)s: %(message)s",
    )
    # bleak and colmi_r02_client log every raw BLE packet at INFO; quiet them down so
    # the primary log output is our own "Heart rate: N bpm" line, not packet dumps.
    if not args.debug:
        logging.getLogger("bleak").setLevel(logging.WARNING)
        logging.getLogger("colmi_r02_client").setLevel(logging.WARNING)

    try:
        asyncio.run(run(args.address, args.osc_ip, args.osc_port, args.reconnect_delay))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
