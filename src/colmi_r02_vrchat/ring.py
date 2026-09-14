"""Continuous real-time heart rate streaming from a Colmi R02 ring.

colmi_r02_client.Client.get_realtime_reading() only returns a short batch of
readings (it sends a start packet, waits for the ring to report up to 6
non-zero values or ~40s to pass, then sends a stop packet). To get a
continuous stream we simply call it back-to-back for as long as the BLE
connection stays up, and transparently reconnect if the ring drops out
(out of range, low battery, etc).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from bleak.exc import BleakError
from colmi_r02_client.client import Client
from colmi_r02_client.real_time import RealTimeReading

logger = logging.getLogger(__name__)

# Errors that mean "the BLE link is gone, try reconnecting" rather than a bug.
CONNECTION_ERRORS = (BleakError, asyncio.TimeoutError, OSError, EOFError)


@dataclass
class Connected:
    pass


@dataclass
class Disconnected:
    error: Exception | None = None


@dataclass
class HeartRate:
    bpm: int


@dataclass
class NoReading:
    """A polling cycle finished without a valid (non-zero) reading, e.g. ring not worn."""


RingEvent = Connected | Disconnected | HeartRate | NoReading


async def stream_heart_rate(address: str, reconnect_delay: float = 5.0) -> AsyncIterator[RingEvent]:
    """Yield heart rate events from the ring forever, reconnecting on failure."""

    while True:
        try:
            async with Client(address) as client:
                logger.info(f"Connected to ring at {address}")
                yield Connected()

                while True:
                    readings = await client.get_realtime_reading(RealTimeReading.HEART_RATE)
                    if not readings:
                        yield NoReading()
                        continue

                    for bpm in readings:
                        yield HeartRate(bpm)
        except CONNECTION_ERRORS as e:
            logger.warning(f"Lost connection to ring: {e!r}. Reconnecting in {reconnect_delay}s")
            yield Disconnected(error=e)
            await asyncio.sleep(reconnect_delay)
