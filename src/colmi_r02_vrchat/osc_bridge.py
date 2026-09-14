"""Send heart rate data to VRChat over OSC.

Follows the de-facto parameter convention popularized by vrc-osc-miband-hrm,
so any avatar already set up for that tool (or similar ones like
PulsoidToOSC / HeartRateOnStream-OSC) works out of the box:

    Heartrate   float, -1..1   (0-255bpm) - precise, meant for a bpm display
    Heartrate2  float,  0..1   (0-255bpm) - coarser, meant for driving animations
    Heartrate3  int,    0..255 (0-255bpm) - raw bpm, meant for threshold logic

isHRConnected / isHRActive are a common extension (used by e.g.
HeartRateOnStream-OSC) for showing ring/device connection state on the avatar;
they are optional and can simply be left unbound in the avatar's parameters.
"""

import logging

from pythonosc.udp_client import SimpleUDPClient

logger = logging.getLogger(__name__)

MAX_BPM = 255


class VRChatOSC:
    def __init__(self, ip: str = "127.0.0.1", port: int = 9000) -> None:
        self._client = SimpleUDPClient(ip, port)

    def send_heart_rate(self, bpm: int) -> None:
        bpm = max(0, min(MAX_BPM, bpm))
        self._client.send_message("/avatar/parameters/Heartrate", (bpm / MAX_BPM) * 2 - 1)
        self._client.send_message("/avatar/parameters/Heartrate2", bpm / MAX_BPM)
        self._client.send_message("/avatar/parameters/Heartrate3", bpm)
        logger.debug(f"Sent heart rate {bpm} bpm over OSC")

    def send_connected(self, connected: bool) -> None:
        self._client.send_message("/avatar/parameters/isHRConnected", connected)
        if not connected:
            self.send_active(False)

    def send_active(self, active: bool) -> None:
        self._client.send_message("/avatar/parameters/isHRActive", active)
