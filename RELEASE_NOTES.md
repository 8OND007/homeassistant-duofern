# Release v2.2.9

## Umweltsensor Fixes: Weather Data & Battery Status

Fixes a bug where weather readings and battery status from the Umweltsensor (0x69) were silently dropped.

The Umweltsensor is a "channel" device: DuoFern stores it as two sub-channels — "00" for the weather station and "01" for the actor. The coordinator's weather-data and battery-status handlers were looking up device state under the bare 6-character device code, which never matches a channel device's 8-character (device code + channel) storage key, so incoming frames found no matching state and were discarded.

- Weather readings (temperature, humidity, brightness, etc.) are now matched to the correct "00" sub-channel and update the corresponding sensor entities as expected.
- Battery status is a whole-device property but channel devices store it per sub-channel, so battery state/percentage is now mirrored onto every registered sub-channel of a channel device. Non-channel devices are unaffected.
- Sensor entities are no longer created on the Umweltsensor's "01" actor sub-channel, since it never receives weather data — this removes dead entities that previously showed no state.

No configuration changes are required; existing Umweltsensor devices will start reporting correctly after updating.
