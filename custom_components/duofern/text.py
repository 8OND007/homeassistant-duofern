"""Text platform for DuoFern.

Provides a text input entity on the stick device card for entering a
6-digit hex device code before triggering pair-by-code.

The text entity is read by DuoFernPairByCodeButton in button.py when
the user presses the "Pair by Code" button.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DuoFernConfigEntry
from .const import DOMAIN
from .coordinator import DuoFernCoordinator, DuoFernDeviceState
from .protocol import DuoFernId

_LOGGER = logging.getLogger(__name__)

# Pattern: exactly 6 hex characters (case-insensitive)
DEVICE_CODE_PATTERN = r"^([0-9A-Fa-f]{6})?$"  # empty or exactly 6 hex chars


@dataclass(frozen=True)
class DuoFernTriggerTextDescription:
    """Describes one trigger-threshold text entity for the Umweltsensor (channel 00).

    All trigger thresholds are space-separated 5-value strings matching
    the FHEM %wCmds set command input format (e.g. "off 15 off off off").
    """

    key: str
    translation_key: str
    name: str
    reading_key: str
    coordinator_method: str
    icon: str
    native_max: int = 100  # longest realistic value: "292.5:180 292.5:180 292.5:180 292.5:180 292.5:180"


# One entry per wCmds trigger field on Umweltsensor channel "00".
# From 30_DUOFERN.pm %setsUmweltsensor00 and %wCmds — all require writeConfig to push to device.
TRIGGER_DESCRIPTIONS: tuple[DuoFernTriggerTextDescription, ...] = (
    DuoFernTriggerTextDescription(
        key="triggerWind",
        translation_key="trigger_wind",
        name="Wind Triggers",
        reading_key="triggerWind",
        coordinator_method="async_set_trigger_wind",
        icon="mdi:weather-windy",
        # Format: "off 15 off off off" (5 channels: off or 1-31 m/s)
        native_max=50,
    ),
    DuoFernTriggerTextDescription(
        key="triggerTemperature",
        translation_key="trigger_temperature",
        name="Temperature Triggers",
        reading_key="triggerTemperature",
        coordinator_method="async_set_trigger_temperature",
        icon="mdi:thermometer-alert",
        # Format: "off -5 22 off off" (off or -40..80°C)
        native_max=60,
    ),
    DuoFernTriggerTextDescription(
        key="triggerDawn",
        translation_key="trigger_dawn",
        name="Dawn Triggers",
        reading_key="triggerDawn",
        coordinator_method="async_set_trigger_dawn",
        icon="mdi:weather-sunset-up",
        # Format: "off 50 off off off" (off or 1-100)
        native_max=50,
    ),
    DuoFernTriggerTextDescription(
        key="triggerDusk",
        translation_key="trigger_dusk",
        name="Dusk Triggers",
        reading_key="triggerDusk",
        coordinator_method="async_set_trigger_dusk",
        icon="mdi:weather-sunset-down",
        # Format: "off 50 off off off" (off or 1-100)
        native_max=50,
    ),
    DuoFernTriggerTextDescription(
        key="triggerSun",
        translation_key="trigger_sun",
        name="Sun Triggers",
        reading_key="triggerSun",
        coordinator_method="async_set_trigger_sun",
        icon="mdi:white-balance-sunny",
        # Format: "off 50:5:5 off off off" or with optional temp "off 50:5:5:10 off off off"
        native_max=100,
    ),
    DuoFernTriggerTextDescription(
        key="triggerSunDirection",
        translation_key="trigger_sun_direction",
        name="Sun Direction Triggers",
        reading_key="triggerSunDirection",
        coordinator_method="async_set_trigger_sun_direction",
        icon="mdi:sun-compass",
        # Format: "off 90:90 off off off" (startAngle:width)
        native_max=80,
    ),
    DuoFernTriggerTextDescription(
        key="triggerSunHeight",
        translation_key="trigger_sun_height",
        name="Sun Height Triggers",
        reading_key="triggerSunHeight",
        coordinator_method="async_set_trigger_sun_height",
        icon="mdi:weather-sunny-alert",
        # Format: "off 13:26 off off off" (fromAngle:widthAngle)
        native_max=60,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuoFernConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DuoFern text entities."""
    coordinator: DuoFernCoordinator = entry.runtime_data
    system_code_hex = coordinator.system_code.hex

    entities: list[TextEntity] = [DuoFernPairCodeText(coordinator, system_code_hex)]

    # Trigger threshold text entities for Umweltsensor channel "00" only.
    # From 30_DUOFERN.pm %setsUmweltsensor00 / %wCmds — these write to local
    # weather_config_registers; changes are pushed to the device via writeConfig.
    for hex_code, device_state in coordinator.data.devices.items():
        if (
            device_state.device_code.device_type == 0x69
            and device_state.channel == "00"
        ):
            dev_code = device_state.device_code
            for desc in TRIGGER_DESCRIPTIONS:
                entities.append(
                    DuoFernTriggerText(
                        coordinator, device_state, hex_code, dev_code, desc
                    )
                )
            break  # only one Umweltsensor expected; avoid duplicates if multiple paired

    coordinator.data.registered_unique_ids.update(
        e._attr_unique_id for e in entities if hasattr(e, "_attr_unique_id")
    )
    async_add_entities(entities)


class DuoFernPairCodeText(CoordinatorEntity[DuoFernCoordinator], TextEntity):
    """Text input for entering a 6-digit hex device code before pair-by-code.

    Appears on the stick device card alongside the "Pair by Code" button.
    The button reads the current value of this entity when pressed.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "pair_code_input"
    _attr_icon = "mdi:barcode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0  # empty string allowed as initial state
    _attr_native_max = 6
    _attr_pattern = DEVICE_CODE_PATTERN

    def __init__(self, coordinator: DuoFernCoordinator, system_code_hex: str) -> None:
        """Initialize the pair code text input."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{system_code_hex}_pair_code_input"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, system_code_hex)})
        self._current_value: str = ""

    @property
    def native_value(self) -> str:
        """Return the current code value."""
        return self._current_value

    async def async_set_value(self, value: str) -> None:
        """Store and validate the entered code.

        HA enforces the pattern on the frontend, but we also validate here
        as a safety net and normalise to uppercase.
        """
        value = value.upper().strip()
        if not re.match(r"^[0-9A-Fa-f]{6}$", value):
            _LOGGER.warning(
                "Invalid device code entered: %r — must be exactly 6 hex characters",
                value,
            )
            return
        self._current_value = value
        self.async_write_ha_state()


class DuoFernTriggerText(CoordinatorEntity[DuoFernCoordinator], TextEntity):
    """Text entity for Umweltsensor trigger threshold configuration (channel "00").

    Exposes the 7 multi-channel trigger settings from 30_DUOFERN.pm %wCmds as
    space-separated 5-value text fields, matching FHEM's input format exactly.

    Values are stored locally in weather_config_registers and pushed to the
    device via the "Konfiguration schreiben" (writeConfig) button. Changes are
    immediately reflected in the entity state via coordinator update.

    Entities appear under EntityCategory.CONFIG (not visible on main dashboard).
    They become available as soon as the Umweltsensor channel "00" is registered;
    the initial state "off off off off off" reflects uninitialized registers.
    After getConfig + writeConfig round-trip the values reflect device state.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0

    def __init__(
        self,
        coordinator: DuoFernCoordinator,
        device_state: DuoFernDeviceState,
        hex_code: str,
        device_code: DuoFernId,
        description: DuoFernTriggerTextDescription,
    ) -> None:
        super().__init__(coordinator)
        self._hex_code = hex_code
        self._device_code = device_code
        self._desc = description
        self._attr_unique_id = f"{DOMAIN}_{hex_code}_{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_icon = description.icon
        self._attr_native_max = description.native_max
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, hex_code)})
        # Default before first getConfig response: all channels off
        self._current_value: str = "off off off off off"

    @property
    def _device_state(self) -> DuoFernDeviceState | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.devices.get(self._hex_code)

    @property
    def available(self) -> bool:
        """Available when channel 00 device state is present."""
        return self._device_state is not None

    @property
    def native_value(self) -> str:
        """Return the decoded trigger value string from config registers."""
        state = self._device_state
        if state is not None:
            val = state.status.readings.get(self._desc.reading_key)
            if val is not None:
                self._current_value = str(val)
        return self._current_value

    async def async_set_value(self, value: str) -> None:
        """Write the new trigger values to the local config registers.

        Calls the coordinator method (async_set_trigger_*) which encodes the
        space-separated value string into the appropriate wCmds register fields.
        Changes are not sent to the device until writeConfig is pressed.
        """
        method = getattr(self.coordinator, self._desc.coordinator_method)
        await method(self._device_code, value)
