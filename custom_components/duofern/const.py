"""Constants for the DuoFern integration."""

from __future__ import annotations

from typing import Final

# Integration domain
DOMAIN: Final = "duofern"

# USB device identification (FTDI FT232R used by Rademacher)
USB_VID: Final = 0x0403  # Future Technology Devices International (FTDI)
USB_PID: Final = 0x6001  # FT232 Serial (UART) IC
USB_PRODUCT: Final = "DuoFern USB-Stick"
USB_MANUFACTURER: Final = "Rademacher"

# Serial communication
SERIAL_BAUDRATE: Final = 115200

# DuoFern protocol constants
FRAME_SIZE_HEX: Final = 44  # 22 bytes = 44 hex characters
FRAME_SIZE_BYTES: Final = 22

# Dongle serial format: must start with "6F" + 4 hex digits
DONGLE_SERIAL_PREFIX: Final = "6F"

# Timing constants (seconds)
ACK_TIMEOUT: Final = 5.0
INIT_RETRY_COUNT: Final = 4
PAIR_TIMEOUT: Final = 60.0
STATUS_TIMEOUT: Final = 30.0
FLUSH_BUFFER_TIMEOUT: Final = 0.5

# Config flow
CONF_SERIAL_PORT: Final = "serial_port"
CONF_DEVICE_CODE: Final = "system_code"
CONF_PAIRED_DEVICES: Final = "paired_devices"

# Device type registry (from 30_DUOFERN.pm %devices)
# Only including types relevant for roller shutters initially
DEVICE_TYPES: Final[dict[int, str]] = {
    0x40: "RolloTron Standard",
    0x41: "RolloTron Comfort Slave",
    0x42: "Rohrmotor-Aktor",
    0x43: "Universalaktor",
    0x46: "Steckdosenaktor",
    0x47: "Rohrmotor Steuerung",
    0x48: "Dimmaktor",
    0x49: "Rohrmotor",
    0x4A: "Dimmer (9476-1)",
    0x4B: "Connect-Aktor",
    0x4C: "Troll Basis",
    0x4E: "SX5",
    0x61: "RolloTron Comfort Master",
    0x62: "Super Fake Device",
    0x65: "Bewegungsmelder",
    0x69: "Umweltsensor",
    0x70: "Troll Comfort DuoFern",
    0x71: "Troll Comfort DuoFern (Lichtmodus)",
    0x73: "Raumthermostat",
    0x74: "Wandtaster 6fach 230V",
    0xA0: "Handsender (6 Gruppen-48 Geraete)",
    0xA1: "Handsender (1 Gruppe-48 Geraete)",
    0xA2: "Handsender (6 Gruppen-1 Geraet)",
    0xA3: "Handsender (1 Gruppe-1 Geraet)",
    0xA4: "Wandtaster",
    0xA5: "Sonnensensor",
    0xA7: "Funksender UP",
    0xA8: "HomeTimer",
    0xA9: "Sonnen-/Windsensor",
    0xAA: "Markisenwaechter",
    0xAB: "Rauchmelder",
    0xAC: "Fenster-Tuer-Kontakt",
    0xAD: "Wandtaster 6fach Bat",
    0xAF: "Sonnensensor",
    0xE0: "Handzentrale",
    0xE1: "Heizkoerperantrieb",
}

# Device types that are roller shutters / covers
COVER_DEVICE_TYPES: Final[set[int]] = {
    0x40,  # RolloTron Standard
    0x41,  # RolloTron Comfort Slave
    0x42,  # Rohrmotor-Aktor
    0x47,  # Rohrmotor Steuerung
    0x49,  # Rohrmotor
    0x4B,  # Connect-Aktor
    0x4C,  # Troll Basis
    0x4E,  # SX5
    0x61,  # RolloTron Comfort Master
    0x70,  # Troll Comfort DuoFern
}

# Status format groups (from 30_DUOFERN.pm %statusGroups)
# Format "21" is used for device type 0x40 (RolloTron Standard)
STATUS_FORMAT_DEFAULT: Final = "21"
