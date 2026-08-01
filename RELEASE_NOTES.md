# Release v2.3.2

- **Umweltsensor dawn/dusk trigger events** — two new event entities ("Dawn"/"Dusk") fire on the "00" sub-channel when the device's dawn/dusk sensorMsg is received. Unlike Sun/Wind/Temperature/Rain, FHEM has no "end" message for these two, so they're modeled as momentary event triggers rather than a persistent on/off sensor. The active Grenzwert slot(s) (1–5) are decoded and passed as extra event data.

- **Active-Grenzwerte sensors for Sun/Wind/Temperature** — these now report which of the up to 5 configured trigger thresholds are currently active, as a comma-joined list (e.g. `"1,3"`), instead of a plain on/off boolean — the sensorMsg channel byte is actually a 5-bit bitmask of triggered slots, not a device channel.

- **Rain binary sensor now also reacts to threshold events** — "Rain Detected" previously only read the continuous `isRaining` bit from weather frames. It now also decodes `startRain`/`endRain` threshold events and combines both with OR. The verified weather-frame bit always wins, so it can't get stuck on "raining" for more than one weather-frame interval (~1 min).

- **Coordinator fix** — Umweltsensor sensorMsg events are now correctly redirected to the "00" sub-channel, matching FHEM's own device-lookup behavior. Previously they were looked up and fired under the bare device code and never reached the "00" sub-channel entities.

- **Known limitation** — the Umweltsensor dawn/dusk and active-Grenzwerte features are translated directly from `30_DUOFERN.pm` but have not yet been verified against a real device.
