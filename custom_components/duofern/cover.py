"""Cover platform for DuoFern roller shutters.

Each paired DuoFern roller shutter device becomes a CoverEntity with:
  - Open / Close / Stop / Set Position
  - Position reporting (0 = closed, 100 = open in HA convention)
  - Moving state (opening / closing / stopped)
  - Device info linked to the hub (USB stick) via via_device

Position inversion:
  DuoFern native: 0 = fully open, 100 = fully closed
  Home Assistant:  0 = fully closed, 100 = fully open
  This module handles the conversion transparently.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DuoFernConfigEntry
from .const import DOMAIN
from .coordinator import DuoFernCoordinator, DuoFernData, DuoFernDeviceState
from .protocol import DuoFernId

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuoFernConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DuoFern cover entities from a config entry."""
    coordinator: DuoFernCoordinator = entry.runtime_data

    entities: list[DuoFernCover] = []
    for hex_code, device_state in coordinator.data.devices.items():
        if device_state.device_code.is_cover:
            entities.append(
                DuoFernCover(
                    coordinator=coordinator,
                    device_code=device_state.device_code,
                    entry_id=entry.entry_id,
                )
            )
            _LOGGER.debug("Adding cover entity for device %s", hex_code)

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d DuoFern cover entities", len(entities))
    else:
        _LOGGER.warning("No cover devices found in paired device list")


class DuoFernCover(CoordinatorEntity[DuoFernCoordinator], CoverEntity):
    """Representation of a DuoFern roller shutter as a HA Cover entity.

    Inherits from CoordinatorEntity for automatic state updates when
    the coordinator pushes new data via async_set_updated_data().
    """

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_has_entity_name = True
    _attr_name = None  # Use device name as entity name

    def __init__(
        self,
        coordinator: DuoFernCoordinator,
        device_code: DuoFernId,
        entry_id: str,
    ) -> None:
        """Initialize the cover entity."""
        super().__init__(coordinator)

        self._device_code = device_code
        self._hex_code = device_code.hex

        # Unique ID: domain + device code
        self._attr_unique_id = f"{DOMAIN}_{self._hex_code}"

        # Device info for the device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._hex_code)},
            name=f"DuoFern {device_code.device_type_name} ({self._hex_code})",
            manufacturer="Rademacher",
            model=device_code.device_type_name,
            sw_version=None,  # Updated when status is received
            via_device=(DOMAIN, coordinator.system_code.hex),
        )

    @property
    def _device_state(self) -> DuoFernDeviceState | None:
        """Get the current device state from the coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.devices.get(self._hex_code)

    # ------------------------------------------------------------------
    # CoverEntity properties
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        state = self._device_state
        if state is None:
            return False
        return state.available and self.coordinator.last_update_success

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        HA convention: 0 = closed, 100 = open.
        DuoFern native: 0 = open, 100 = closed.
        So we invert: ha_position = 100 - duofern_position
        """
        state = self._device_state
        if state is None or state.status.position is None:
            return None
        return 100 - state.status.position

    @property
    def is_closed(self) -> bool | None:
        """Return True if the cover is fully closed."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    @property
    def is_opening(self) -> bool:
        """Return True if the cover is currently opening."""
        state = self._device_state
        if state is None:
            return False
        return state.status.moving == "up"

    @property
    def is_closing(self) -> bool:
        """Return True if the cover is currently closing."""
        state = self._device_state
        if state is None:
            return False
        return state.status.moving == "down"

    # ------------------------------------------------------------------
    # CoverEntity commands
    # ------------------------------------------------------------------

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (move up)."""
        await self.coordinator.async_cover_up(self._device_code)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover (move down)."""
        await self.coordinator.async_cover_down(self._device_code)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        await self.coordinator.async_cover_stop(self._device_code)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position.

        HA sends position as 0=closed, 100=open.
        DuoFern expects 0=open, 100=closed.
        So we invert: duofern_position = 100 - ha_position
        """
        ha_position: int = kwargs.get("position", 0)
        duofern_position = 100 - ha_position
        await self.coordinator.async_cover_position(
            self._device_code, duofern_position
        )

    # ------------------------------------------------------------------
    # Coordinator entity callbacks
    # ------------------------------------------------------------------

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Called automatically by CoordinatorEntity when the coordinator
        calls async_set_updated_data().
        """
        state = self._device_state
        if state and state.status.version:
            # Update firmware version in device info if available
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._hex_code)},
                name=f"DuoFern {self._device_code.device_type_name} ({self._hex_code})",
                manufacturer="Rademacher",
                model=self._device_code.device_type_name,
                sw_version=state.status.version,
                via_device=(DOMAIN, self.coordinator.system_code.hex),
            )

        self.async_write_ha_state()
