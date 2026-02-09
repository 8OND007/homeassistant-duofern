"""DuoFern protocol encoder/decoder.

Pure protocol logic with no Home Assistant or asyncio dependencies.
All frame construction uses bytearray for safety; no fragile string replacement.

Frame format: 22 bytes (44 hex characters)
  - Byte 0:    Message type / command class
  - Byte 1-10: Payload (command-specific)
  - Byte 11-12: Reserved (zeros)
  - Byte 13-15: Dongle serial (system code, "zzzzzz")
  - Byte 16-18: Device code ("yyyyyy")
  - Byte 19-21: Flags / channel / trailer

Reference: 10_DUOFERNSTICK.pm and 30_DUOFERN.pm from FHEM
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum

from .const import (
    COVER_DEVICE_TYPES,
    DEVICE_TYPES,
    FRAME_SIZE_BYTES,
    FRAME_SIZE_HEX,
    STATUS_FORMAT_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DuoFernId:
    """A 3-byte identifier (device code or system code) stored as bytes."""

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != 3:
            raise ValueError(f"DuoFernId must be 3 bytes, got {len(self.raw)}")

    @classmethod
    def from_hex(cls, hex_str: str) -> DuoFernId:
        """Create from a 6-character hex string like '6F1A2B'."""
        if len(hex_str) != 6:
            raise ValueError(f"Expected 6 hex chars, got {len(hex_str)}: {hex_str}")
        return cls(raw=bytes.fromhex(hex_str))

    @property
    def hex(self) -> str:
        """Return uppercase hex representation."""
        return self.raw.hex().upper()

    @property
    def device_type(self) -> int:
        """Return the first byte (device type)."""
        return self.raw[0]

    @property
    def device_type_name(self) -> str:
        """Return human-readable device type name."""
        return DEVICE_TYPES.get(self.raw[0], f"Unknown (0x{self.raw[0]:02X})")

    @property
    def is_cover(self) -> bool:
        """Return True if this device type is a roller shutter / cover."""
        return self.raw[0] in COVER_DEVICE_TYPES

    def __repr__(self) -> str:
        return f"DuoFernId({self.hex})"

    def __hash__(self) -> int:
        return hash(self.raw)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DuoFernId):
            return self.raw == other.raw
        return NotImplemented


@dataclass
class DeviceStatus:
    """Parsed status of a DuoFern cover device."""

    # Position 0 = fully open, 100 = fully closed (DuoFern native)
    # HA inversion is done in cover.py, not here
    position: int | None = None
    moving: str = "stop"  # "stop", "up", "down"

    # Automation flags
    time_automatic: bool | None = None
    sun_automatic: bool | None = None
    dawn_automatic: bool | None = None
    dusk_automatic: bool | None = None
    manual_mode: bool | None = None
    ventilating_mode: bool | None = None
    sun_mode: bool | None = None

    # Special positions
    sun_position: int | None = None
    ventilating_position: int | None = None

    # Firmware version
    version: str | None = None


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CoverCommand(IntEnum):
    """Cover command codes from 30_DUOFERN.pm %commands."""

    UP = 0x0701
    STOP = 0x0702
    DOWN = 0x0703
    POSITION = 0x0707
    TOGGLE = 0x071A


class MessageType(IntEnum):
    """Top-level message type classification."""

    INIT1 = 0x01
    SET_PAIRS = 0x03
    START_PAIR = 0x04
    STOP_PAIR = 0x05
    PAIR_RESPONSE = 0x06
    START_UNPAIR = 0x07
    STOP_UNPAIR = 0x08
    SET_DONGLE = 0x0A
    COMMAND = 0x0D
    INIT2 = 0x0E
    STATUS = 0x0F
    INIT_END = 0x10
    INIT3 = 0x14
    ACK = 0x81


# ---------------------------------------------------------------------------
# Encoder - builds raw frames as bytearray
# ---------------------------------------------------------------------------

class DuoFernEncoder:
    """Builds DuoFern protocol frames.

    All methods return a bytearray of exactly 22 bytes.
    The FHEM Perl code uses string replacement (s/zzzzzz/.../) which is
    error-prone. We use explicit byte placement instead.
    """

    @staticmethod
    def _frame() -> bytearray:
        """Return a zeroed 22-byte frame."""
        return bytearray(FRAME_SIZE_BYTES)

    # -- Initialization sequence (from DUOFERNSTICK_DoInit) --

    @staticmethod
    def build_init1() -> bytearray:
        """Step 1: duoInit1 = '01000000...'."""
        frame = DuoFernEncoder._frame()
        frame[0] = 0x01
        return frame

    @staticmethod
    def build_init2() -> bytearray:
        """Step 2: duoInit2 = '0E000000...'."""
        frame = DuoFernEncoder._frame()
        frame[0] = 0x0E
        return frame

    @staticmethod
    def build_set_dongle(system_code: DuoFernId) -> bytearray:
        """Step 3: duoSetDongle = '0Azzzzzz000100...'

        Places system code at bytes 1-3, then 0x0001 at bytes 4-5.
        """
        frame = DuoFernEncoder._frame()
        frame[0] = 0x0A
        frame[1:4] = system_code.raw
        frame[4] = 0x00
        frame[5] = 0x01
        return frame

    @staticmethod
    def build_init3() -> bytearray:
        """Step 4: duoInit3 = '14140000...'."""
        frame = DuoFernEncoder._frame()
        frame[0] = 0x14
        frame[1] = 0x14
        return frame

    @staticmethod
    def build_set_pair(index: int, device_code: DuoFernId) -> bytearray:
        """Step 5 (repeated): duoSetPairs = '03nnyyyyyy0000...'

        index: 0-based pair slot number
        device_code: 6-digit device code
        """
        frame = DuoFernEncoder._frame()
        frame[0] = 0x03
        frame[1] = index & 0xFF
        frame[2:5] = device_code.raw
        return frame

    @staticmethod
    def build_init_end() -> bytearray:
        """Step 6: duoInitEnd = '10010000...'."""
        frame = DuoFernEncoder._frame()
        frame[0] = 0x10
        frame[1] = 0x01
        return frame

    @staticmethod
    def build_ack() -> bytearray:
        """ACK frame: duoACK = '81000000...'."""
        frame = DuoFernEncoder._frame()
        frame[0] = 0x81
        return frame

    # -- Operational commands --

    @staticmethod
    def build_status_request_broadcast() -> bytearray:
        """Broadcast status request: duoStatusRequest.

        '0DFF0F400000000000000000000000000000FFFFFF01'
        Bytes 0-3:   0D FF 0F 40 (header)
        Bytes 4-14:  zeros
        Bytes 15-17: zeros (no system code for broadcast)
        Bytes 18-20: FF FF FF (broadcast address)
        Byte 21:     01
        """
        frame = DuoFernEncoder._frame()
        frame[0] = 0x0D
        frame[1] = 0xFF
        frame[2] = 0x0F
        frame[3] = 0x40
        # bytes 4-17: zeros (already zeroed)
        frame[18] = 0xFF  # broadcast device code
        frame[19] = 0xFF
        frame[20] = 0xFF
        frame[21] = 0x01
        return frame

    @staticmethod
    def build_status_request(
        device_code: DuoFernId,
        system_code: DuoFernId,
        status_type: int = 0x0F,
    ) -> bytearray:
        """Per-device status request.

        Template from 30_DUOFERN.pm:
          $duoStatusRequest = "0DFFnn400000000000000000000000000000yyyyyy01"
        Where nn = status type, yyyyyy = device code.
        Note: NO system code in this template (bytes 15-17 stay zero).
        cc = FF (primary channel), device code at bytes 18-20.
        """
        frame = DuoFernEncoder._frame()
        frame[0] = 0x0D
        frame[1] = 0xFF  # channel = FF (primary device)
        frame[2] = status_type
        frame[3] = 0x40
        # bytes 4-17: zeros (no system code for status requests)
        frame[18:21] = device_code.raw
        frame[21] = 0x01
        return frame

    @staticmethod
    def build_cover_command(
        command: CoverCommand,
        device_code: DuoFernId,
        system_code: DuoFernId,
        position: int | None = None,
        timer: bool = False,
        channel: int = 0x01,
    ) -> bytearray:
        """Build a cover command frame.

        Template from 30_DUOFERN.pm:
          duoCommand = '0Dccnnnnnnnnnnnnnnnnnnnn000000zzzzzzyyyyyy00'
        Where:
          cc = channel number (byte 1)
          nnnnnnnnnnnnnnnnnnnn = 10-byte command payload (bytes 2-11)
          bytes 12-13 = 0x0000 (reserved)
          zzzzzz = system code (bytes 14-16)  -- NOTE: actually 13-15 in 0-indexed
          yyyyyy = device code (bytes 17-19)  -- NOTE: actually 16-18
          byte 20-21 = 0x00

        The command payload is built from %commands:
          up    = '0701tt00000000000000'
          stop  = '07020000000000000000'
          down  = '0703tt00000000000000'
          pos   = '0707ttnn000000000000' (nn = position value, 0=open 100=closed)
          toggle= '071A0000000000000000'
        """
        frame = DuoFernEncoder._frame()

        # Byte 0: message type 0x0D (command)
        frame[0] = 0x0D

        # Byte 1: channel
        frame[1] = channel

        # Bytes 2-11: command payload
        cmd_high = (command >> 8) & 0xFF
        cmd_low = command & 0xFF
        frame[2] = cmd_high
        frame[3] = cmd_low

        # Timer flag at byte 4
        timer_byte = 0x01 if timer else 0x00
        if command in (CoverCommand.UP, CoverCommand.DOWN):
            frame[4] = timer_byte
        elif command == CoverCommand.POSITION:
            frame[4] = timer_byte
            # Position value at byte 5 (caller handles inversion)
            if position is not None:
                clamped = max(0, min(100, position))
                frame[5] = clamped
            else:
                _LOGGER.warning("POSITION command without position value")
                frame[5] = 0
        # STOP and TOGGLE have no extra parameters

        # Bytes 12-13: reserved (already zero)

        # Bytes 14-16: system code (dongle serial)
        # Looking at the FHEM template more carefully:
        # '0Dccnnnnnnnnnnnnnnnnnnnn000000zzzzzzyyyyyy00'
        #  0  1  2                    12    14    17   20
        # bytes 2-11 = command (10 bytes)
        # bytes 12-13 = 0x0000
        # bytes 14-16 = system code (zzzzzz = 3 bytes)
        # bytes 17-19 = device code (yyyyyy = 3 bytes)
        # bytes 20-21 = 0x0000
        #
        # Wait - let me recount the template:
        # 0D cc nnnnnnnnnnnnnnnnnnnn 000000 zzzzzz yyyyyy 00
        # 1  1  10                   3      3      3      1 = 22 bytes  OK!

        frame[12] = 0x00
        frame[13] = 0x00
        frame[14] = 0x00

        frame[15:18] = system_code.raw
        frame[18:21] = device_code.raw
        frame[21] = 0x00

        return frame

    @staticmethod
    def build_start_pair() -> bytearray:
        """Start pairing mode: duoStartPair = '04000000...'."""
        frame = DuoFernEncoder._frame()
        frame[0] = 0x04
        return frame

    @staticmethod
    def build_stop_pair() -> bytearray:
        """Stop pairing mode: duoStopPair = '05000000...'."""
        frame = DuoFernEncoder._frame()
        frame[0] = 0x05
        return frame

    @staticmethod
    def build_start_unpair() -> bytearray:
        """Start unpairing mode: duoStartUnpair = '07000000...'."""
        frame = DuoFernEncoder._frame()
        frame[0] = 0x07
        return frame

    @staticmethod
    def build_stop_unpair() -> bytearray:
        """Stop unpairing mode: duoStopUnpair = '08000000...'."""
        frame = DuoFernEncoder._frame()
        frame[0] = 0x08
        return frame


# ---------------------------------------------------------------------------
# Decoder - parses raw frames
# ---------------------------------------------------------------------------

class DuoFernDecoder:
    """Parses DuoFern protocol frames.

    Input is always a bytearray of 22 bytes or a 44-char hex string.
    """

    @staticmethod
    def _ensure_bytes(data: bytes | bytearray | str) -> bytearray:
        """Convert hex string or bytes to bytearray."""
        if isinstance(data, str):
            if len(data) != FRAME_SIZE_HEX:
                raise ValueError(
                    f"Hex string must be {FRAME_SIZE_HEX} chars, got {len(data)}"
                )
            return bytearray.fromhex(data)
        if isinstance(data, (bytes, bytearray)):
            if len(data) != FRAME_SIZE_BYTES:
                raise ValueError(
                    f"Frame must be {FRAME_SIZE_BYTES} bytes, got {len(data)}"
                )
            return bytearray(data)
        raise TypeError(f"Unsupported type: {type(data)}")

    @staticmethod
    def is_ack(data: bytes | bytearray | str) -> bool:
        """Check if frame is an ACK (0x81...)."""
        frame = DuoFernDecoder._ensure_bytes(data)
        return frame[0] == MessageType.ACK

    @staticmethod
    def classify_message(data: bytes | bytearray | str) -> MessageType | int:
        """Return the message type byte."""
        frame = DuoFernDecoder._ensure_bytes(data)
        try:
            return MessageType(frame[0])
        except ValueError:
            return frame[0]

    @staticmethod
    def extract_device_code(data: bytes | bytearray | str) -> DuoFernId:
        """Extract the 3-byte device code from a frame.

        From DUOFERN_Parse: code = substr($msg, 30, 6)
        Hex position 30-35 = byte position 15-17

        BUT for ACK messages: code = substr($msg, 36, 6) => bytes 18-20
        """
        frame = DuoFernDecoder._ensure_bytes(data)
        if frame[0] == MessageType.ACK:
            return DuoFernId(raw=bytes(frame[18:21]))
        return DuoFernId(raw=bytes(frame[15:18]))

    @staticmethod
    def extract_device_code_from_status(data: bytes | bytearray | str) -> DuoFernId:
        """Extract device code specifically from status messages.

        Status messages (0x0F prefix) have device code at hex pos 30-35 = bytes 15-17
        """
        frame = DuoFernDecoder._ensure_bytes(data)
        return DuoFernId(raw=bytes(frame[15:18]))

    @staticmethod
    def is_status_response(data: bytes | bytearray | str) -> bool:
        """Check if frame is an actor status response.

        Pattern from FHEM: $msg =~ m/0FFF0F.{38}/
        Byte 0 = 0x0F, Byte 1 = 0xFF, Byte 2 = 0x0F
        """
        frame = DuoFernDecoder._ensure_bytes(data)
        return frame[0] == 0x0F and frame[1] == 0xFF and frame[2] == 0x0F

    @staticmethod
    def is_pair_response(data: bytes | bytearray | str) -> bool:
        """Check if frame is a pair notification. Pattern: 0602..."""
        frame = DuoFernDecoder._ensure_bytes(data)
        return frame[0] == 0x06 and frame[1] == 0x02

    @staticmethod
    def is_unpair_response(data: bytes | bytearray | str) -> bool:
        """Check if frame is an unpair notification. Pattern: 0603..."""
        frame = DuoFernDecoder._ensure_bytes(data)
        return frame[0] == 0x06 and frame[1] == 0x03

    @staticmethod
    def is_broadcast_status_ack(data: bytes | bytearray | str) -> bool:
        """Check if this is the broadcast status ack we can ignore.

        Pattern: 0FFF11...
        """
        frame = DuoFernDecoder._ensure_bytes(data)
        return frame[0] == 0x0F and frame[1] == 0xFF and frame[2] == 0x11

    @staticmethod
    def parse_status_type40(
        data: bytes | bytearray | str,
    ) -> DeviceStatus:
        """Parse status message for device type 0x40 (RolloTron Standard).

        Status format "21" from 30_DUOFERN.pm:
          statusGroup "21" => [100, 101, 102, 104, 105, 106, 111, 112, 113, 114, 50]

        Key fields for type 40 (channel "01"):
          102 = position:    byte_pos=7, bits 0-6, invert=100
          50  = moving:      byte_pos=0, bits 0-0
          100 = sunAutomatic:   byte_pos=0, bits 2-2
          101 = timeAutomatic:  byte_pos=0, bits 0-0
          104 = duskAutomatic:  byte_pos=0, bits 3-3
          105 = dawnAutomatic:  byte_pos=1, bits 3-3
          106 = manualMode:     byte_pos=0, bits 7-7
          111 = sunPosition:    byte_pos=6, bits 0-6, invert=100
          112 = ventilatingPos: byte_pos=2, bits 0-6, invert=100
          113 = ventilatingMode:byte_pos=2, bits 7-7
          114 = sunMode:        byte_pos=6, bits 7-7

        The "position" in the message payload:
          Status message: 0FFF0F <format> <payload...> <code>
          Byte 0 = 0x0F, Byte 1 = 0xFF, Byte 2 = 0x0F, Byte 3 = format
          Payload starts at byte 3 after the 0FFF0F prefix

          In the Perl code:
            $value = hex(substr($msg, 6 + $stPos*2, 4))
          hex position 6 = byte 3 of frame. So "position 0" in statusIds
          refers to frame byte 3, "position 7" = frame byte 10.

          More precisely: the 16-bit word at hex offset (6 + pos*2) is read,
          which is bytes (3 + pos) and (3 + pos + 1) of the frame.
          Then bits from..to are extracted.
        """
        frame = DuoFernDecoder._ensure_bytes(data)
        status = DeviceStatus()

        if not DuoFernDecoder.is_status_response(frame):
            _LOGGER.warning("Not a status response: %s", frame.hex())
            return status

        # Helper to read a 16-bit value from the payload
        # "position N" in FHEM = byte offset (3 + N) in the frame
        # reading 2 bytes (big-endian 16-bit)
        def read_word(pos: int) -> int:
            byte_offset = 3 + pos
            if byte_offset + 1 >= FRAME_SIZE_BYTES:
                return 0
            return (frame[byte_offset] << 8) | frame[byte_offset + 1]

        def extract_bits(word: int, from_bit: int, to_bit: int) -> int:
            length = to_bit - from_bit + 1
            return (word >> from_bit) & ((1 << length) - 1)

        # Firmware version: byte 12 (hex pos 24-25)
        # In FHEM: substr($msg, 24, 1).".".substr($msg, 25, 1)
        ver_byte = frame[12]
        status.version = f"{(ver_byte >> 4) & 0x0F}.{ver_byte & 0x0F}"

        # Position (statusId 102): pos=7, bits 0-6, invert=100
        word7 = read_word(7)
        raw_position = extract_bits(word7, 0, 6)
        status.position = raw_position  # Native DuoFern: 0=open, 100=closed

        # Moving (statusId 50): pos=0, bits 0-0
        word0 = read_word(0)
        moving_bit = extract_bits(word0, 0, 0)
        # In FHEM: moving map = ["stop", "stop"] -- bit just indicates activity
        # Actual direction must be inferred from position changes
        status.moving = "stop"  # Will be refined by coordinator

        # Time automatic (statusId 101): pos=0, bits 0-0
        # Wait - this overlaps with moving? Let me re-check FHEM:
        # statusId 50  = moving:        pos=0, from=0, to=0
        # statusId 101 = timeAutomatic: pos=0, from=0, to=0
        # These are DIFFERENT statusIds evaluated for different formats.
        # Format "21" includes: [100,101,102,104,105,106,111,112,113,114,50]
        # So both 101 and 50 are in format 21, and both read pos=0, bit 0.
        # This seems like a conflict in FHEM. Let's check statusId 100 instead:
        # statusId 100 = sunAutomatic:  pos=0, from=2, to=2
        # statusId 101 = timeAutomatic: pos=0, from=0, to=0  -- same as moving!
        #
        # Looking more carefully at the FHEM parse code, it iterates ALL statusIds
        # in the group and the LAST write wins for same-named readings.
        # For format "21": both 50(moving) and 101(timeAutomatic) read bit 0 of word 0.
        # The reading names are different so both get stored.
        #
        # This means: timeAutomatic and the moving flag share the SAME bit.
        # This is likely a firmware quirk - the moving bit IS timeAutomatic.
        # Let's just store both.
        status.time_automatic = bool(extract_bits(word0, 0, 0))

        # Sun automatic (statusId 100): pos=0, bits 2-2
        status.sun_automatic = bool(extract_bits(word0, 2, 2))

        # Dusk automatic (statusId 104): pos=0, bits 3-3
        status.dusk_automatic = bool(extract_bits(word0, 3, 3))

        # Manual mode (statusId 106): pos=0, bits 7-7
        status.manual_mode = bool(extract_bits(word0, 7, 7))

        # Dawn automatic (statusId 105): pos=1, bits 3-3
        word1 = read_word(1)
        status.dawn_automatic = bool(extract_bits(word1, 3, 3))

        # Ventilating position (statusId 112): pos=2, bits 0-6, invert=100
        word2 = read_word(2)
        raw_vent = extract_bits(word2, 0, 6)
        status.ventilating_position = raw_vent

        # Ventilating mode (statusId 113): pos=2, bits 7-7
        status.ventilating_mode = bool(extract_bits(word2, 7, 7))

        # Sun position (statusId 111): pos=6, bits 0-6, invert=100
        word6 = read_word(6)
        raw_sun_pos = extract_bits(word6, 0, 6)
        status.sun_position = raw_sun_pos

        # Sun mode (statusId 114): pos=6, bits 7-7
        status.sun_mode = bool(extract_bits(word6, 7, 7))

        return status

    @staticmethod
    def parse_status(
        data: bytes | bytearray | str,
    ) -> DeviceStatus:
        """Parse a status message, auto-detecting device type.

        Currently only supports format "21" (type 0x40 etc.).
        Falls back to type40 parsing for all cover types.
        """
        frame = DuoFernDecoder._ensure_bytes(data)
        device_code = DuoFernDecoder.extract_device_code_from_status(frame)

        # For now, all cover types use the same format "21" parsing
        if device_code.is_cover:
            return DuoFernDecoder.parse_status_type40(frame)

        _LOGGER.debug(
            "Unsupported device type for status parsing: %s (%s)",
            device_code.hex,
            device_code.device_type_name,
        )
        return DeviceStatus()

    @staticmethod
    def should_dispatch(data: bytes | bytearray | str) -> bool:
        """Check if this message should be dispatched to device handlers.

        From DUOFERNSTICK_Parse:
          - ACKs (81...) are consumed by the write queue handler
          - Pair/unpair responses (0602/0603) are handled specially
          - Broadcast status ack (0FFF11...) is ignored
          - Everything else is dispatched
        """
        frame = DuoFernDecoder._ensure_bytes(data)

        # ACK - handled by write queue
        if frame[0] == 0x81:
            return False

        # Broadcast status ack - ignore
        if frame[0] == 0x0F and frame[1] == 0xFF and frame[2] == 0x11:
            return False

        return True


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def frame_to_hex(frame: bytearray) -> str:
    """Convert a frame bytearray to uppercase hex string."""
    return frame.hex().upper()


def hex_to_frame(hex_str: str) -> bytearray:
    """Convert a hex string to a frame bytearray."""
    return bytearray.fromhex(hex_str)


def validate_system_code(code: str) -> bool:
    """Validate a system code (must be 6 hex chars starting with '6F')."""
    if len(code) != 6:
        return False
    try:
        bytes.fromhex(code)
    except ValueError:
        return False
    return code.upper().startswith("6F")


def validate_device_code(code: str) -> bool:
    """Validate a device code (must be 6 hex chars)."""
    if len(code) != 6:
        return False
    try:
        bytes.fromhex(code)
    except ValueError:
        return False
    return True
