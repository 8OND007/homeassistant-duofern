# Release v2.2.7

## Network Serial Support (ser2net)

The integration now supports connecting to the DuoFern USB stick over a network via `ser2net`, in addition to the existing direct USB connection. This is useful when running Home Assistant in a virtualised environment (e.g. Proxmox VM) while the USB stick is physically connected to another machine on the local network.

Two network protocols are supported:

- **`socket://host:port`** — raw TCP connection (recommended); uses the same fast async transport as a local USB port
- **`rfc2217://host:port`** — RFC2217 network serial; uses a worker-thread transport to work around PySerial's blocking RFC2217 implementation

Existing USB connections (`/dev/ttyUSB0`, etc.) are **fully unaffected** — `socket://` goes through the same fast async path as local USB, and the new threaded transport is only used for `rfc2217://` URLs.

The config flow serial port field now shows discovered local USB ports as dropdown suggestions while also allowing a network URL to be typed freely.

Thanks to [@MBj1703](https://github.com/MBj1703) for the original pull request on the upstream repository.
