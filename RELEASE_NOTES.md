# Release v2.3.1

## Umweltsensor (0x69) — Device Clock, Full Register Writes & Trigger Configuration

This release rounds out the Umweltsensor config story started in v2.3.0: latitude/longitude/timezone/DCF/rain-trigger are now written into the real device registers instead of a stub, all 7 multi-channel trigger thresholds (wind, temperature, dawn, dusk, sun, sun direction, sun height) get dedicated text entities, the device's internal clock can be read back, and the actor sub-channel ("01") gets a full set of automation switches and position numbers matching a Rohrmotor/Troll cover.

### Device Date & Time Sensors

Pressing the **Get Time** button now populates two new diagnostic sensors on the weather station sub-channel ("00"):

| Entity | Source |
|--------|--------|
| Device Date | `date` reading, e.g. `2026-07-30` |
| Device Time | `time` reading, e.g. `15:30:00` |

Decoded from the Umweltsensor's Zeit response frame (`0F..1020…`), translated from `30_DUOFERN.pm`. The device encodes each field as BCD (e.g. byte `0x26` means "26", not 38), so the parser formats each byte as a 2-digit hex string rather than a decimal value.

### Full Config Register Writes (Latitude / Longitude / Timezone / DCF / Rain Trigger)

Previously, latitude, longitude, and timezone went through a stub (`async_set_umweltsensor_number`) that only logged the value, and DCF / interval / rain-trigger were stored as plain reading strings that were never actually encoded into the registers `writeConfig` sends to the device.

All five now write directly into the correct bits of the device's config register pages (`weather_config_registers`, keyed by register index 0–7), matching the `%wCmds` bit layout from `30_DUOFERN.pm`:

| Setting | Register | Byte | Encoding |
|---------|----------|------|----------|
| Latitude | reg7 | byte 5 | unsigned 0–90 |
| Longitude | reg7 | byte 7 | signed −90–90, stored as `value + 256` when negative |
| Timezone | reg7 | byte 4 | unsigned 0–23 |
| DCF | reg7 | byte 1 | bit 1 |
| Interval | reg7 | byte 0 | bit 7 = enabled, bits 6–0 = minutes (or clear bit 7 for "off") |
| Trigger Rain | reg6 | byte 0 | bit 7 |

`writeConfig` was rewritten to read from this per-channel register store (on the "00" sub-channel) instead of `.reg0`–`.reg7` readings on the bare device code, and now validates each register's length before sending.

### 7 New Trigger Threshold Text Entities

The remaining multi-channel trigger fields from `%wCmds` are now exposed as text entities on channel "00", using the same space-separated 5-value format FHEM itself expects:

| Entity | Format | Range |
|--------|--------|-------|
| Wind Triggers | `off 15 off off off` | 1–31 m/s per channel |
| Temperature Triggers | `off -5 22 off off` | −40–80 °C per channel |
| Dawn Triggers | `off 50 off off off` | 1–100 (brightness) per channel |
| Dusk Triggers | `off 50 off off off` | 1–100 (brightness) per channel |
| Sun Triggers | `off 50:5:5 off off off` | `kLux:sunMin:shadowMin[:minTemp]` |
| Sun Direction Triggers | `off 90:90 off off off` | `startAngle:width` (22.5°/45° steps) |
| Sun Height Triggers | `off 13:26 off off off` | `fromAngle:widthAngle` (13°/26° steps) |

Each entity encodes its value straight into the corresponding config register bits; nothing is sent to the device until the **writeConfig** button is pressed.

Multi-channel updates are now batched — new `_raw_update_reg_byte` / `_raw_update_reg_word32` helpers write all 5 channels into memory first, then `_flush_weather_config()` re-decodes and notifies Home Assistant exactly once per call instead of once per channel.

### Actor Sub-Channel ("01") — Position Numbers & Automation Switches

The Umweltsensor's actor sub-channel behaves like a Rohrmotor/Troll cover, so it now gets the matching entity set:

- **Numbers:** Sun Position, Ventilating Position (0–100 %)
- **Automation switches:** Manual Mode, Time Automatic, Dawn Automatic, Dusk Automatic, Sun Automatic, Sun Mode, Ventilating Mode

These use the standard format-23a command set (`async_set_sun_position`, `async_set_ventilating_position`, `async_set_automation`), identical to how other covers handle the same commands.
