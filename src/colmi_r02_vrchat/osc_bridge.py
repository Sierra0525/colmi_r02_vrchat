"""Send heart rate data to VRChat over OSC.

Uses the same OSC parameter paths as nullstalgia's iron-heart
(https://github.com/nullstalgia/iron-heart), which HeartOSC also mirrors
for compatibility and which avatar prefabs such as PIXEL PULSE
(https://pixelpulse.nsuke5.workers.dev/) are built to consume, so avatars
already set up for those tools work with this bridge unchanged:

    isHRConnected    bool            ring is connected over BLE
    HeartBeatToggle  bool            flips every time a new reading arrives
    isHRBeat         bool            true for `pulse_length` seconds per reading
    HR               int,   0-255    current bpm
    floatHR          float, -1..1    current bpm, normalized

Note: the Colmi R02's real-time API only reports periodic averaged bpm
samples, not individual heartbeat/RR-interval events like a standard BLE
Heart Rate Service device, so HeartBeatToggle/isHRBeat fire once per
received sample rather than on the true, individual heartbeat.
"""

from __future__ import annotations

import asyncio
import logging

from pythonosc.udp_client import SimpleUDPClient

logger = logging.getLogger(__name__)

PREFIX = "/avatar/parameters/"
MAX_BPM = 255


class VRChatOSC:
    def __init__(self, ip: str = "127.0.0.1", port: int = 9000, pulse_length: float = 0.1) -> None:
        self._client = SimpleUDPClient(ip, port)
        self._pulse_length = pulse_length
        self._beat_toggle = False
        self._pulse_task: asyncio.Task[None] | None = None

    def _send(self, name: str, value: bool | int | float) -> None:
        self._client.send_message(PREFIX + name, value)

    def send_connected(self, connected: bool) -> None:
        self._send("isHRConnected", connected)
        if not connected:
            if self._pulse_task is not None:
                self._pulse_task.cancel()
                self._pulse_task = None
            self._send("isHRBeat", False)

    def send_heart_rate(self, bpm: int) -> None:
        bpm = max(0, min(MAX_BPM, bpm))
        self._send("HR", bpm)
        self._send("floatHR", (bpm / MAX_BPM) * 2 - 1)

        self._beat_toggle = not self._beat_toggle
        self._send("HeartBeatToggle", self._beat_toggle)

        if self._pulse_task is not None:
            self._pulse_task.cancel()
        self._send("isHRBeat", True)
        self._pulse_task = asyncio.create_task(self._reset_pulse())

        logger.debug(f"Sent heart rate {bpm} bpm over OSC")

    async def _reset_pulse(self) -> None:
        await asyncio.sleep(self._pulse_length)
        self._send("isHRBeat", False)
