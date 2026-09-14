"""Continuous real-time heart rate streaming from a Colmi R02 ring.

colmi_r02_client.Client.get_realtime_reading() sends a single start packet
and then just listens, never sending the "continue" packet that the ring's
protocol also defines (colmi_r02_client.real_time.get_continue_packet /
Action.CONTINUE). In practice some rings stop reporting new samples and drop
the BLE connection after roughly 30-40 seconds of a real-time session that
nothing "continues" (observed as one HeartRate reading of 0, then silence,
then a disconnect). So instead of using that helper, we drive the
start/continue/stop protocol ourselves and send a continue packet at least
once a second to keep the session alive, and reconnect if the ring still
drops out (out of range, low battery, etc).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from bleak.exc import BleakError
from colmi_r02_client import real_time
from colmi_r02_client.client import Client
from colmi_r02_client.real_time import RealTimeReading

logger = logging.getLogger(__name__)

# Errors that mean "the BLE link is gone, try reconnecting" rather than a bug.
CONNECTION_ERRORS = (BleakError, asyncio.TimeoutError, OSError, EOFError)

# How often to send a "continue" packet to keep the ring's real-time session alive.
CONTINUE_INTERVAL = 1.0


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
    """No valid (non-zero) reading arrived this cycle, e.g. ring not worn/settling."""


RingEvent = Connected | Disconnected | HeartRate | NoReading


async def stream_heart_rate(address: str, reconnect_delay: float = 5.0) -> AsyncIterator[RingEvent]:
    """Yield heart rate events from the ring forever, reconnecting on failure."""

    reading_type = RealTimeReading.HEART_RATE

    while True:
        try:
            async with Client(address) as client:
                logger.info(f"Connected to ring at {address}")
                yield Connected()

                await client.send_packet(real_time.get_start_packet(reading_type))
                queue = client.queues[real_time.CMD_START_REAL_TIME]

                try:
                    while True:
                        # The ring acks a continue packet almost instantly, so pacing this
                        # purely off the queue wait would spam continue packets back-to-back
                        # as fast as the ring replies. Send one, wait (generously) for its
                        # ack, then explicitly sleep out the rest of CONTINUE_INTERVAL so we
                        # poll at roughly a fixed ~1x/s rate regardless of ack latency.
                        loop_start = asyncio.get_running_loop().time()
                        await client.send_packet(real_time.get_continue_packet(reading_type))
                        try:
                            data = await asyncio.wait_for(queue.get(), timeout=2.0)
                        except asyncio.TimeoutError:
                            data = None

                        if data is None:
                            yield NoReading()
                        elif isinstance(data, real_time.ReadingError):
                            logger.warning(f"Ring reported an error for {data.kind.name}: code {data.code}")
                            yield NoReading()
                        elif data.value == 0:
                            yield NoReading()
                        else:
                            yield HeartRate(data.value)

                        elapsed = asyncio.get_running_loop().time() - loop_start
                        await asyncio.sleep(max(0.0, CONTINUE_INTERVAL - elapsed))
                finally:
                    try:
                        await client.send_packet(real_time.get_stop_packet(reading_type))
                    except CONNECTION_ERRORS:
                        pass
        except CONNECTION_ERRORS as e:
            logger.warning(f"Lost connection to ring: {e!r}. Reconnecting in {reconnect_delay}s")
            yield Disconnected(error=e)
            await asyncio.sleep(reconnect_delay)
