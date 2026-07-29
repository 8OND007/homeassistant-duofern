# Release v2.3.0

## Umweltsensor (0x69) — Full Config & Actor Support

This release completes the Umweltsensor integration: config registers are now decoded from `getConfig` responses, a rain binary sensor is added, and the actor sub-channel gets its own set of entities. It also fixes misrouted rain events from v2.2.9.

### Rain Binary Sensor

A new **Rain Detected** binary sensor (`device_class: moisture`) is now created for the Umweltsensor's weather station sub-channel ("00"). It has two update paths:

- **Coordinator push** — reads `isRaining` from the weather frame (bit 15 of the temperature word, decoded every ~1 minute).
- **Event bus** — reacts instantly to `startRain` / `endRain` events fired by the coordinator between regular weather frames.

The last known state is restored across HA restarts via `RestoreEntity`.

### Weather Config Register Decode

The coordinator now handles `getConfig` responses from the Umweltsensor (frame pattern `0FFF1B2[1-8]`). The device sends 8 separate register pages; each page is stored and the full config is re-decoded after every received page (missing pages default to all-zero, same as FHEM).

Decoded readings land on the "00" sub-channel and immediately populate the existing config entities:

| Reading | Source | Entity |
|---------|--------|--------|
| `interval` | reg7 byte 0 | Transmit Interval select |
| `DCF` | reg7 byte 1 bit 1 | DCF Time Sync switch |
| `timezone` | reg7 byte 4 | Timezone number |
| `latitude` | reg7 byte 5 (signed) | Latitude number |
| `longitude` | reg7 byte 7 (signed) | Longitude number |
| `triggerRain` | reg6 byte 0 bit 7 | Trigger Rain switch |
| `triggerWind` | reg6 bytes 0–4 | — (5 channels) |
| `triggerTemperature` | reg6 bytes 5–9 | — (5 channels) |
| `triggerDawn` / `triggerDusk` | regs 0–2 | — (5 channels each) |
| `triggerSun` / `triggerSunDirection` / `triggerSunHeight` | regs 3–5 | — (5 channels each) |

Translated faithfully from `DUOFERN_DecodeWeatherSensorConfig()` in `30_DUOFERN.pm`.

### Actor Sub-Channel ("01") Entities

The Umweltsensor's actor sub-channel now gets its own entities matching `%setsUmweltsensor01` from `30_DUOFERN.pm`:

| Entity | Type | Description |
|--------|------|-------------|
| Running Time | Number (0–100 s) | Motor running time |
| Wind Direction | Select (up/down) | Movement direction on wind trigger |
| Rain Direction | Select (up/down) | Movement direction on rain trigger |
| Wind Automatic | Switch | Enable wind-triggered automation |
| Rain Automatic | Switch | Enable rain-triggered automation |
| Wind Mode | Switch | Wind mode flag |
| Rain Mode | Switch | Rain mode flag |
| Reversal | Switch | Reversal flag |

### Channel Separation (channel_filter)

All entity descriptions for the Umweltsensor now carry an explicit `channel_filter` that restricts creation to the correct sub-channel:

- Config entities (interval, DCF, triggerRain, latitude, longitude, timezone) → channel "00" only
- Actor entities (running time, wind/rain direction, automation flags) → channel "01" only

This eliminates duplicate entities that previously appeared on both sub-channels.

### Bug Fix: Rain Event Channel

The `startRain` and `endRain` events fired by `_handle_weather_data()` were emitting `device_code = bare_hex` with `channel = "01"`. They now emit `device_code = bare_hex + "00"` with `channel = "00"`, so the rain binary sensor (which uses the 8-character channel key as its identifier) matches correctly.
