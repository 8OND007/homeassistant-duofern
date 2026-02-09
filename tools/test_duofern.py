#!/usr/bin/env python3
"""Standalone test script for DuoFern roller shutter control.

Tests the protocol and stick layer directly, without Home Assistant.
Run this on the Raspberry Pi where the DuoFern USB stick is connected.

Requirements:
    pip install pyserial pyserial-asyncio-fast

Usage:
    python3 test_duofern.py <device_code> <command> [position]

Examples:
    python3 test_duofern.py 4053B8 up
    python3 test_duofern.py 4053B8 down
    python3 test_duofern.py 4053B8 stop
    python3 test_duofern.py 4053B8 position 50
    python3 test_duofern.py 4053B8 status

Device codes (from your FHEM config):
    406B0D  Rolladentuer        (Wohnzimmer)
    4090EA  Rolladenfenster     (Wohnzimmer)
    40B689  Rolladenfensterklein (Wohnzimmer Esstisch)
    4053B8  az_Rolladentuer     (Arbeitszimmer)
    4083D8  kz_Rolladenfenster  (Kinderzimmer)
    409C11  sz_Rolladenfenster  (Schlafzimmer)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

# ---------------------------------------------------------------------------
# Direct module loading — bypasses __init__.py (which needs homeassistant)
# ---------------------------------------------------------------------------
import importlib.util
import types

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(SCRIPT_DIR)  # Go up from tools/ to repo root
_DUOFERN_PKG = os.path.join(_REPO_ROOT, "custom_components", "duofern")


def _load_module(name: str) -> types.ModuleType:
    """Load a duofern module directly by file path, bypassing __init__.py."""
    fqn = f"custom_components.duofern.{name}"
    spec = importlib.util.spec_from_file_location(
        fqn, os.path.join(_DUOFERN_PKG, f"{name}.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[fqn] = mod
    spec.loader.exec_module(mod)
    return mod


# Create fake package hierarchy so relative imports inside the modules work
# (e.g. stick.py does "from .const import ..." which resolves to
#  "custom_components.duofern.const")
_pkg_cc = types.ModuleType("custom_components")
_pkg_cc.__path__ = [os.path.join(_REPO_ROOT, "custom_components")]
sys.modules["custom_components"] = _pkg_cc

_pkg_df = types.ModuleType("custom_components.duofern")
_pkg_df.__path__ = [_DUOFERN_PKG]
sys.modules["custom_components.duofern"] = _pkg_df

# Load in dependency order: const → protocol → stick
_const = _load_module("const")
_protocol = _load_module("protocol")
_stick = _load_module("stick")

# Pull symbols into local namespace (same names as before)
SERIAL_BAUDRATE = _const.SERIAL_BAUDRATE
CoverCommand = _protocol.CoverCommand
DuoFernDecoder = _protocol.DuoFernDecoder
DuoFernEncoder = _protocol.DuoFernEncoder
DuoFernId = _protocol.DuoFernId
frame_to_hex = _protocol.frame_to_hex
validate_device_code = _protocol.validate_device_code
validate_system_code = _protocol.validate_system_code
DuoFernStick = _stick.DuoFernStick

# ---------------------------------------------------------------------------
# Configuration — adjust these to match your setup
# ---------------------------------------------------------------------------
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
DEFAULT_SYSTEM_CODE = "6F1A2B"

# All known paired devices (registered during init handshake)
PAIRED_DEVICES = [
    "406B0D",  # Rolladentuer (Wohnzimmer)
    "4090EA",  # Rolladenfenster (Wohnzimmer)
    "40B689",  # Rolladenfensterklein (Wohnzimmer Esstisch)
    "4053B8",  # az_Rolladentuer (Arbeitszimmer)
    "4083D8",  # kz_Rolladenfenster (Kinderzimmer)
    "409C11",  # sz_Rolladenfenster (Schlafzimmer)
]

# How long to wait for status responses after sending a command (seconds)
STATUS_WAIT_TIME = 10.0


# ---------------------------------------------------------------------------
# Message handler: prints incoming messages
# ---------------------------------------------------------------------------
def on_message(frame: bytearray) -> None:
    """Handle incoming messages from the stick."""
    hex_str = frame_to_hex(frame)

    if DuoFernDecoder.is_status_response(frame):
        device_code = DuoFernDecoder.extract_device_code_from_status(frame)
        status = DuoFernDecoder.parse_status(frame)
        print(f"\n{'='*60}")
        print(f"  STATUS from {device_code.hex} ({device_code.device_type_name})")
        print(f"  Position:    {status.position}%"
              f" (DuoFern: 0=open, 100=closed)")
        print(f"  Moving:      {status.moving}")
        print(f"  Version:     {status.version}")
        print(f"  Automatics:  time={status.time_automatic}"
              f" sun={status.sun_automatic}"
              f" dawn={status.dawn_automatic}"
              f" dusk={status.dusk_automatic}")
        print(f"  Manual mode: {status.manual_mode}")
        print(f"  Raw:         {hex_str}")
        print(f"{'='*60}")
    elif DuoFernDecoder.is_pair_response(frame):
        code = DuoFernDecoder.extract_device_code(frame)
        print(f"  PAIR response from {code.hex}")
    elif DuoFernDecoder.is_unpair_response(frame):
        code = DuoFernDecoder.extract_device_code(frame)
        print(f"  UNPAIR response from {code.hex}")
    else:
        print(f"  MSG: {hex_str}")


# ---------------------------------------------------------------------------
# Main async logic
# ---------------------------------------------------------------------------
async def run(args: argparse.Namespace) -> None:
    """Connect to stick, send command, wait for response."""
    system_code = DuoFernId.from_hex(args.system_code)
    device_code = DuoFernId.from_hex(args.device)
    paired = [DuoFernId.from_hex(d) for d in PAIRED_DEVICES]

    # Make sure target device is in paired list
    if args.device.upper() not in [d.upper() for d in PAIRED_DEVICES]:
        print(f"WARNING: Device {args.device} is not in PAIRED_DEVICES list!")
        print(f"         The stick might not be able to reach it.")
        print(f"         Add it to PAIRED_DEVICES in this script.\n")

    print(f"DuoFern Test Script")
    print(f"  Port:        {args.port}")
    print(f"  System code: {args.system_code}")
    print(f"  Device:      {args.device} ({device_code.device_type_name})")
    print(f"  Command:     {args.command}", end="")
    if args.command == "position":
        print(f" {args.position}%")
    else:
        print()
    print()

    # Create and connect stick
    print("Connecting to DuoFern stick...")
    stick = DuoFernStick(
        port=args.port,
        system_code=system_code,
        paired_devices=paired,
        message_callback=on_message,
    )

    try:
        await stick.connect()
        print("Connected and initialized!\n")
    except Exception as err:
        print(f"\nERROR: Failed to connect: {err}")
        print(f"\nTroubleshooting:")
        print(f"  - Is the USB stick plugged in?")
        print(f"  - Check: ls -la {args.port}")
        print(f"  - Check permissions: groups $(whoami)")
        print(f"  - Try: sudo chmod 666 {args.port}")
        sys.exit(1)

    try:
        # Build and send command
        if args.command == "up":
            print(f">> Sending UP to {args.device}...")
            frame = DuoFernEncoder.build_cover_command(
                CoverCommand.UP, device_code, system_code
            )
            await stick.send_command(frame)

        elif args.command == "down":
            print(f">> Sending DOWN to {args.device}...")
            frame = DuoFernEncoder.build_cover_command(
                CoverCommand.DOWN, device_code, system_code
            )
            await stick.send_command(frame)

        elif args.command == "stop":
            print(f">> Sending STOP to {args.device}...")
            frame = DuoFernEncoder.build_cover_command(
                CoverCommand.STOP, device_code, system_code
            )
            await stick.send_command(frame)

        elif args.command == "position":
            pos = args.position
            print(f">> Sending POSITION {pos}% to {args.device}...")
            print(f"   (DuoFern value: {100 - pos}, because 0=open, 100=closed)")
            frame = DuoFernEncoder.build_cover_command(
                CoverCommand.POSITION, device_code, system_code,
                position=100 - pos,  # Convert: user says 0=closed, 100=open
            )
            await stick.send_command(frame)

        elif args.command == "status":
            print(f">> Requesting status from {args.device}...")
            frame = DuoFernEncoder.build_status_request(
                device_code, system_code
            )
            await stick.send_command(frame)

        elif args.command == "statusall":
            print(f">> Broadcasting status request to all devices...")
            frame = DuoFernEncoder.build_status_request_broadcast()
            await stick.send_command(frame)

        print(f"\nCommand sent. Waiting {STATUS_WAIT_TIME}s for responses...\n")
        await asyncio.sleep(STATUS_WAIT_TIME)

    except Exception as err:
        print(f"\nERROR: {err}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nDisconnecting...")
        await stick.disconnect()
        print("Done.")


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------
def main() -> None:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(
        description="DuoFern roller shutter test script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Device codes (from FHEM config):
  406B0D  Rolladentuer         (Wohnzimmer)
  4090EA  Rolladenfenster      (Wohnzimmer)
  40B689  Rolladenfensterklein (Wohnzimmer Esstisch)
  4053B8  az_Rolladentuer      (Arbeitszimmer)
  4083D8  kz_Rolladenfenster   (Kinderzimmer)
  409C11  sz_Rolladenfenster   (Schlafzimmer)

Examples:
  python3 test_duofern.py 4053B8 up
  python3 test_duofern.py 4053B8 down
  python3 test_duofern.py 4053B8 stop
  python3 test_duofern.py 4053B8 position 50
  python3 test_duofern.py 4053B8 status
  python3 test_duofern.py 406B0D statusall
        """,
    )

    parser.add_argument(
        "device",
        help="Device code (6 hex chars, e.g. 4053B8)",
    )
    parser.add_argument(
        "command",
        choices=["up", "down", "stop", "position", "status", "statusall"],
        help="Command to send",
    )
    parser.add_argument(
        "position",
        nargs="?",
        type=int,
        default=50,
        help="Position 0-100 (only for 'position' command, 0=closed, 100=open)",
    )
    parser.add_argument(
        "--port", "-p",
        default=DEFAULT_SERIAL_PORT,
        help=f"Serial port (default: {DEFAULT_SERIAL_PORT})",
    )
    parser.add_argument(
        "--system-code", "-s",
        default=DEFAULT_SYSTEM_CODE,
        help=f"System code (default: {DEFAULT_SYSTEM_CODE})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Validate inputs
    args.device = args.device.upper()
    args.system_code = args.system_code.upper()

    if not validate_device_code(args.device):
        parser.error(f"Invalid device code: {args.device} (need 6 hex chars)")

    if not validate_system_code(args.system_code):
        parser.error(
            f"Invalid system code: {args.system_code} (need 6 hex chars starting with 6F)"
        )

    if args.command == "position":
        if args.position < 0 or args.position > 100:
            parser.error(f"Position must be 0-100, got {args.position}")

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet down noisy loggers unless verbose
    if not args.verbose:
        logging.getLogger("custom_components.duofern.stick").setLevel(logging.WARNING)
        logging.getLogger("custom_components.duofern.protocol").setLevel(logging.WARNING)

    # Run
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
