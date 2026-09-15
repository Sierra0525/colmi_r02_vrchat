"""Continuous real-time heart rate streaming from a Colmi R02 ring.

colmi_r02_client.real_time models the "start real-time reading" command
(0x69) as [0x69, reading_type, action] with a START/CONTINUE/STOP action
byte and a separate reading-type byte (HEART_RATE=1, SPO2=3, etc). In
testing against a real ring (firmware R02_3.00.17) that never produced a
non-zero reading and eventually dropped the BLE connection, no matter which
reading_type or continue cadence was tried.

Gadgetbridge's actual, working Colmi R0x support (see
service/devices/colmi/ColmiR0xDeviceSupport.java, ported in
https://github.com/jonas-werner/ring-health-tracker/blob/main/app/src/main/java/dev/ring/health/ColmiProtocol.kt)
uses a much simpler protocol for on-demand heart rate that doesn't match
colmi_r02_client's model at all:

    start: make_packet(0x69, [0x01])   # no reading-type byte
    stop:  make_packet(0x69, [0x02])

Once started, the ring streams bpm notifications on its own -- no periodic
"continue" packet needed -- until the stop packet is sent. Response layout
is [0x69, sub, error_code, bpm, ...], where error_code is 0=OK, 1=ring not
worn correctly, 2=temporary error. This module implements that protocol
directly instead of using colmi_r02_client.real_time.
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

CMD_MANUAL_HEART_RATE = 0x69
_START_SUBCMD = 0x01
_STOP_SUBCMD = 0x02

# How long to wait for a notification before assuming something's wrong
# (the ring streams on its own once started, so silence this long is unusual).
READING_TIMEOUT = 5.0

ERROR_NOT_WORN = 1


def _start_packet() -> bytearray:
    return packet_module.make_packet(CMD_MANUAL_HEART_RATE, bytearray([_START_SUBCMD]))


def _stop_packet() -> bytearray:
    return packet_module.make_packet(CMD_MANUAL_HEART_RATE, bytearray([_STOP_SUBCMD]))


@dataclass
class LiveHrReading:
    sub: int
    error_code: int
    bpm: int


def _parse_live_hr_packet(packet: bytearray) -> LiveHrReading:
    assert packet[0] == CMD_MANUAL_HEART_RATE
    return LiveHrReading(sub=packet[1], error_code=packet[2], bpm=packet[3])


# colmi_r02_client's own parser for this command expects a reading-type byte
# that doesn't apply to this simpler start/stop protocol; install a compatible
# one for the manual/live heart rate command.
client_module.COMMAND_HANDLERS[CMD_MANUAL_HEART_RATE] = _parse_live_hr_packet


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

    not_worn: bool = False


RingEvent = Connected | Disconnected | HeartRate | NoReading


async def stream_heart_rate(address: str, reconnect_delay: float = 5.0) -> AsyncIterator[RingEvent]:
    """Yield heart rate events from the ring forever, reconnecting on failure."""

    while True:
        try:
            async with Client(address) as client:
                logger.info(f"Connected to ring at {address}")
                yield Connected()

                await client.send_packet(_start_packet())
                queue = client.queues[CMD_MANUAL_HEART_RATE]

                try:
                    while True:
                        try:
                            data = await asyncio.wait_for(queue.get(), timeout=READING_TIMEOUT)
                        except asyncio.TimeoutError:
                            yield NoReading()
                            continue

                        if data.error_code == ERROR_NOT_WORN:
                            yield NoReading(not_worn=True)
                        elif data.error_code != 0:
                            logger.warning(f"Ring reported error code {data.error_code}")
                            yield NoReading()
                        elif data.bpm == 0:
                            yield NoReading()
                        else:
                            yield HeartRate(data.bpm)
                finally:
                    try:
                        await client.send_packet(_stop_packet())
                    except CONNECTION_ERRORS:
                        pass
        except CONNECTION_ERRORS as e:
            logger.warning(f"Lost connection to ring: {e!r}. Reconnecting in {reconnect_delay}s")
            yield Disconnected(error=e)
            await asyncio.sleep(reconnect_delay)
