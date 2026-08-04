# Release v2.3.4

- **Fixed sun direction angle bug** — the `triggerSunDirection` encoding formula was wrong for most angle/width combinations (integer truncation + an incorrect clamp instead of the real device's natural 4-bit wraparound). Fixed and verified against all 14 of Gerald's confirmed Homepilot angles × 4 confirmed widths (56 combinations, zero mismatches) plus all 3 previously-captured real device bytes.

- **Confirmed/corrected value ranges** — "Sonne erkennen nach"/"Schatten erkennen nach" corrected to 1–32 (was 1–30). Sonnenrichtung target angle converted from a free-form Number to a Select with exactly the 14 valid Homepilot values. All other previously-unconfirmed ranges are now confirmed correct against real Homepilot sliders.

- **Fixed missing entity names** — several Umweltsensor entities were showing only the device name ("Wetterstation") instead of a distinguishing label, and — once translations were added — showed English text even under a German HA language. Both are fixed: entities now rely purely on translation-file names, matching HA's own name-resolution priority.

- **New: per-Grenzwert-slot automation triggers** — Sonne, Wind, Temperatur, Morgendämmerung, and Abenddämmerung each offer dedicated device automation triggers per Grenzwert slot (e.g. "Wind Grenzwert 3 – Start"), selectable directly from the automation editor's dropdown — no template needed. Adds no new entities. Regen is unaffected (stays a flat trigger, no Grenzwert concept there).

- **New: Bewegungsmelder (0x65) and Wandtaster 6fach 230V (0x74) now use two sub-channels each**, matching the Umweltsensor pattern — one for their events (motion / button presses), one for a new switch-actor sub-device (on/off, dusk/dawn buttons, stairwell timer, automation switches). Previously their events were silently dropped due to a channel-routing mismatch.

- **Fixed: Wandtaster 6fach 230V (0x74) only had a working automation trigger for 1 of its 6 buttons** — all 6 are now selectable.

- **New: the Umweltsensor's actor sub-channel is now a properly recognized cover type** — it gets the correct RolloTron-style command set (no reset buttons, matching the real device) instead of being treated like a Rohrmotor/Troll cover, and its moving-state updates immediately instead of lagging until the next status frame.

- **Fixed: an entity could be left behind (orphaned) after a type migration** — entity cleanup now keys on (platform, unique_id) instead of a bare unique_id, so a migration like Number → Select reusing the same ID always cleans up the old entity correctly.

- **New: the paired device codes field is now optional during setup** — you can complete setup with zero devices and add them afterwards via pairing or Configure, useful for a from-scratch setup with no FHEM/Homepilot history to import from.

- **Documentation: added a section on picking a System Code from scratch** when you have neither FHEM history nor Homepilot access to read the original one back.

- **Fixed: window/door contact "opened"/"tilted" sensors could get stuck on** if the window moved directly between those two states without passing through "closed" first. Both now always reflect the correct current state.