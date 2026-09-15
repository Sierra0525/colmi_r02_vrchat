"""Continuous real-time heart rate streaming from a Colmi R02 ring.

There are two entirely separate heart-rate-over-BLE commands on this ring,
confirmed from Gadgetbridge's actual PR adding this support
(service/devices/colmi/ColmiR0xDeviceSupport.java +
devices/colmi/ColmiR0xConstants.java, Freeyourgadget/Gadgetbridge PR #4223):

  CMD_MANUAL_HEART_RATE = 0x69
      A bounded, one-shot "measure now" spot check (what the official app's
      manual measurement, and our earlier implementation, used). It streams
      a handful of samples over up to ~30s and stops; it is not meant to run
      indefinitely.

  CMD_REALTIME_HEART_RATE = 0x1e
      The actual continuous streaming mode (used by Gadgetbridge's "Live
      Activity" tab, which stays open and updating for as long as you're
      looking at it -- exactly the semantics we want for VRChat). Enable
      with subcommand 0x01, disable with 0x02. The session has a 60s
      timeout on the ring's side, so Gadgetbridge sends a "continue"
      subcommand (0x03) every ~30s to keep it alive. Response layout is
      [0x1e, bpm, ...] -- note bpm is at byte[1] here, not byte[3] like the
      manual command.

This module drives CMD_REALTIME_HEART_RATE directly.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from bleak.exc import BleakError
from colmi_r02_client import client as client_module
from colmi_r02_client import packet as packet_module
from colmi_r02_client.client import Client

logger = logging.getLogger(__name__)

# Errors that mean "the BLE link is gone, try reconnecting" rather than a bug.
CONNECTION_ERRORS = (BleakError, asyncio.TimeoutError, OSError, EOFError)

CMD_REALTIME_HEART_RATE = 0x1E
_ENABLE_SUBCMD = 0x01
_DISABLE_SUBCMD = 0x02
_CONTINUE_SUBCMD = 0x03

# The ring times out the realtime session after 60s; send a continue well
# before that (Gadgetbridge does so every ~30s).
CONTINUE_INTERVAL = 20.0

# How long to wait for a notification before giving up on this connection.
# Readings should arrive roughly once a second once enabled.
READING_TIMEOUT = 10.0


def _enable_packet() -> bytearray:
    return packet_module.make_packet(CMD_REALTIME_HEART_RATE, bytearray([_ENABLE_SUBCMD]))


def _disable_packet() -> bytearray:
    return packet_module.make_packet(CMD_REALTIME_HEART_RATE, bytearray([_DISABLE_SUBCMD]))


def _continue_packet() -> bytearray:
    return packet_module.make_packet(CMD_REALTIME_HEART_RATE, bytearray([_CONTINUE_SUBCMD]))


@dataclass
class RealtimeHrReading:
    bpm: int


def _parse_realtime_hr_packet(packet: bytearray) -> RealtimeHrReading:
    assert packet[0] == CMD_REALTIME_HEART_RATE
    return RealtimeHrReading(bpm=packet[1])


client_module.COMMAND_HANDLERS[CMD_REALTIME_HEART_RATE] = _parse_realtime_hr_packet


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

    while True:
        try:
            async with Client(address) as client:
                logger.info(f"Connected to ring at {address}")
                yield Connected()

                await client.send_packet(_enable_packet())
                queue = client.queues[CMD_REALTIME_HEART_RATE]
                last_continue = asyncio.get_running_loop().time()

                try:
                    while True:
                        try:
                            data = await asyncio.wait_for(queue.get(), timeout=READING_TIMEOUT)
                        except asyncio.TimeoutError:
                            data = None

                        now = asyncio.get_running_loop().time()
                        if now - last_continue >= CONTINUE_INTERVAL:
                            await client.send_packet(_continue_packet())
                            last_continue = now

                        if data is None or data.bpm == 0:
                            yield NoReading()
                        else:
                            yield HeartRate(data.bpm)
                finally:
                    try:
                        await client.send_packet(_disable_packet())
                    except CONNECTION_ERRORS:
                        pass
        except CONNECTION_ERRORS as e:
            logger.warning(f"Lost connection to ring: {e!r}. Reconnecting in {reconnect_delay}s")
            yield Disconnected(error=e)
            await asyncio.sleep(reconnect_delay)
