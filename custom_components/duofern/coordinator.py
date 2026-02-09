"""DataUpdateCoordinator for DuoFern integration.

Push-based coordinator: no polling interval. State is updated when the
stick receives messages from devices. We use async_set_updated_data()
to push new state to entities.

The coordinator owns the DuoFernStick instance and manages device state.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .protocol import (
    DeviceStatus,
    DuoFernDecoder,
    DuoFernEncoder,
    DuoFernId,
    CoverCommand,
    frame_to_hex,
)
from .stick import DuoFernStick

_LOGGER = logging.getLogger(__name__)


@dataclass
class DuoFernDeviceState:
    """State for a single DuoFern device."""

    device_code: DuoFernId
    status: DeviceStatus = field(default_factory=DeviceStatus)
    available: bool = True
    last_seen: float | None = None


@dataclass
class DuoFernData:
    """Data container for the coordinator."""

    devices: dict[str, DuoFernDeviceState] = field(default_factory=dict)


class DuoFernCoordinator(DataUpdateCoordinator[DuoFernData]):
    """Coordinator that manages the DuoFern stick and device states.

    This is a push-based coordinator (no polling). State updates come from
    the stick's message callback, and are pushed to entities via
    async_set_updated_data().
    """

    def __init__(
        self,
        hass: HomeAssistant,
        port: str,
        system_code: DuoFernId,
        paired_devices: list[DuoFernId],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # No update_interval = push-based, no polling
        )

        self._port = port
        self._system_code = system_code
        self._paired_devices = paired_devices

        # Initialize device states
        self._data = DuoFernData()
        for device in paired_devices:
            self._data.devices[device.hex] = DuoFernDeviceState(
                device_code=device,
            )

        self.data = self._data

        # The stick will be created in connect()
        self._stick: DuoFernStick | None = None

    @property
    def system_code(self) -> DuoFernId:
        """Return the system code."""
        return self._system_code

    @property
    def stick(self) -> DuoFernStick | None:
        """Return the stick instance."""
        return self._stick

    async def connect(self) -> None:
        """Create and connect the DuoFern stick."""
        self._stick = DuoFernStick(
            port=self._port,
            system_code=self._system_code,
            paired_devices=self._paired_devices,
            message_callback=self._on_message,
        )
        await self._stick.connect()
        _LOGGER.info("DuoFern coordinator connected")

    async def disconnect(self) -> None:
        """Disconnect the DuoFern stick."""
        if self._stick:
            await self._stick.disconnect()
            self._stick = None
        _LOGGER.info("DuoFern coordinator disconnected")

    async def _async_update_data(self) -> DuoFernData:
        """Not used for push-based coordinator, but required by base class."""
        return self._data

    # ------------------------------------------------------------------
    # Device commands
    # ------------------------------------------------------------------

    async def async_cover_up(self, device_code: DuoFernId) -> None:
        """Send UP command to a cover device."""
        frame = DuoFernEncoder.build_cover_command(
            command=CoverCommand.UP,
            device_code=device_code,
            system_code=self._system_code,
        )
        await self._send(frame)

        # Optimistic state update
        self._update_moving_state(device_code, "up")

    async def async_cover_down(self, device_code: DuoFernId) -> None:
        """Send DOWN command to a cover device."""
        frame = DuoFernEncoder.build_cover_command(
            command=CoverCommand.DOWN,
            device_code=device_code,
            system_code=self._system_code,
        )
        await self._send(frame)

        # Optimistic state update
        self._update_moving_state(device_code, "down")

    async def async_cover_stop(self, device_code: DuoFernId) -> None:
        """Send STOP command to a cover device."""
        frame = DuoFernEncoder.build_cover_command(
            command=CoverCommand.STOP,
            device_code=device_code,
            system_code=self._system_code,
        )
        await self._send(frame)

        # Optimistic state update
        self._update_moving_state(device_code, "stop")

    async def async_cover_position(
        self, device_code: DuoFernId, position: int
    ) -> None:
        """Send POSITION command to a cover device.

        position: 0 = open, 100 = closed (DuoFern native convention).
        The HA inversion (0=closed, 100=open) is handled in cover.py.
        """
        frame = DuoFernEncoder.build_cover_command(
            command=CoverCommand.POSITION,
            device_code=device_code,
            system_code=self._system_code,
            position=position,
        )
        await self._send(frame)

        # Optimistic moving direction
        state = self._data.devices.get(device_code.hex)
        if state and state.status.position is not None:
            if position > state.status.position:
                self._update_moving_state(device_code, "down")
            elif position < state.status.position:
                self._update_moving_state(device_code, "up")

    async def async_request_status(
        self, device_code: DuoFernId | None = None
    ) -> None:
        """Request status from a specific device or broadcast to all."""
        if device_code is None:
            frame = DuoFernEncoder.build_status_request_broadcast()
        else:
            frame = DuoFernEncoder.build_status_request(
                device_code=device_code,
                system_code=self._system_code,
            )
        await self._send(frame)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send(self, frame: bytearray) -> None:
        """Send a frame via the stick."""
        if self._stick is None or not self._stick.connected:
            _LOGGER.error("Cannot send: stick not connected")
            return
        await self._stick.send_command(frame)

    @callback
    def _on_message(self, frame: bytearray) -> None:
        """Handle incoming message from the stick.

        Called from the serial protocol in the event loop.
        """
        try:
            if DuoFernDecoder.is_status_response(frame):
                self._handle_status(frame)
            elif DuoFernDecoder.is_pair_response(frame):
                device_code = DuoFernDecoder.extract_device_code(frame)
                _LOGGER.info("Device paired: %s", device_code.hex)
            elif DuoFernDecoder.is_unpair_response(frame):
                device_code = DuoFernDecoder.extract_device_code(frame)
                _LOGGER.info("Device unpaired: %s", device_code.hex)
            else:
                _LOGGER.debug(
                    "Unhandled message type 0x%02X: %s",
                    frame[0],
                    frame_to_hex(frame),
                )
        except Exception:
            _LOGGER.exception(
                "Error handling message: %s", frame_to_hex(frame)
            )

    def _handle_status(self, frame: bytearray) -> None:
        """Parse and store a device status message."""
        device_code = DuoFernDecoder.extract_device_code_from_status(frame)
        hex_code = device_code.hex

        if hex_code not in self._data.devices:
            _LOGGER.debug(
                "Status from unknown device %s, ignoring", hex_code
            )
            return

        status = DuoFernDecoder.parse_status(frame)
        state = self._data.devices[hex_code]
        state.status = status
        state.available = True

        _LOGGER.debug(
            "Status update for %s: position=%s, moving=%s",
            hex_code,
            status.position,
            status.moving,
        )

        # Push update to all entities
        self.async_set_updated_data(self._data)

    def _update_moving_state(
        self, device_code: DuoFernId, direction: str
    ) -> None:
        """Optimistically update the moving state and push to entities."""
        state = self._data.devices.get(device_code.hex)
        if state:
            state.status.moving = direction
            self.async_set_updated_data(self._data)
