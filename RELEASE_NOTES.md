# Release v2.3.3

- **Structured trigger GUI for Umweltsensor (0x69)** — the 7 text-input trigger fields (Wind/Temperature/Dawn/Dusk/Sun Trigger, packing all 5 Grenzwert slots into one string like `off 15 off off off`) are replaced with proper per-slot controls: a **Grenzwert Slot selector** (1–5) per group, a **Number** for the slot's target value, and a **Switch** to enable/disable it. New dedicated selects also cover the sun-direction/-height fields with their fixed, Homepilot-confirmed discrete options. All still write to the same config registers via `writeConfig` — only the GUI changed.

- **Known limitation** — a few of the new value ranges (Sun brightness/delay, "Ab Temperatur von") are derived from the register's bit width rather than confirmed against a real Homepilot slider yet.
