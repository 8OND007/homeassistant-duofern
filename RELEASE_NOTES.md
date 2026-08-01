# Release v2.3.4

- **Fixed sun direction angle bug** — the `triggerSunDirection` encoding formula was wrong for most angle/width combinations (integer truncation + an incorrect clamp instead of the real device's natural 4-bit wraparound). Fixed and verified against all 14 of Gerald's confirmed Homepilot angles × 4 confirmed widths (56 combinations, zero mismatches) plus all 3 previously-captured real device bytes.

- **Confirmed/corrected value ranges** — "Sonne erkennen nach"/"Schatten erkennen nach" corrected to 1–32 (was 1–30). Sonnenrichtung target angle converted from a free-form Number to a Select with exactly the 14 valid Homepilot values. All other previously-unconfirmed ranges are now confirmed correct against real Homepilot sliders.

- **Fixed missing entity names** — three Active-Grenzwerte sensors and the Dawn/Dusk event entity were showing only the device name ("Wetterstation") instead of a distinguishing label, due to a missing translation + fallback name. Fixed.

- **New: per-Grenzwert-slot automation triggers** — Sonne, Wind, Temperatur, Morgendämmerung, and Abenddämmerung each offer dedicated device automation triggers per Grenzwert slot (e.g. "Wind Grenzwert 3 – Start"), selectable directly from the automation editor's dropdown — no template needed. Adds no new entities. Regen is unaffected (stays a flat trigger, no Grenzwert concept there).