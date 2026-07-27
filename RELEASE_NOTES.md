# Release v2.2.8

## Reconfigurable Serial Connection

The serial connection (port or network URL) can now be changed after initial setup without removing and re-adding the integration.

Go to **Settings → Devices & Services → DuoFern → ⋮ → Reconfigure** to update the connection. The form pre-fills the current value, shows discovered local USB ports as dropdown suggestions, and accepts any `socket://` or `rfc2217://` network URL as a custom entry. The connection is validated before saving, and the integration reloads automatically on success.

The system code and paired device list are not affected by reconfiguration.
