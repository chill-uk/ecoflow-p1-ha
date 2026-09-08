# EcoFlow P1 Energy Tracker for Home Assistant

A local-only Home Assistant custom integration for the EcoFlow P1 Energy
Tracker. It reads the raw DSMR telegram from the dongle's local
HTTP endpoint:

```text
GET http://<device-ip>/getdebugdata
```

It does **not** use the EcoFlow cloud API.

## MVP features

- UI configuration by hostname or IP address
- Device identity based on the P1 dongle serial number (`SN`)
- One coordinated HTTP request per update
- Configurable 5–300 second polling interval (5 seconds by default)
- DSMR parsing by OBIS identifier, independent of line order
- Single-phase and three-phase electricity measurements
- Dynamically discovered gas readings on M-Bus channels 1–4
- Dongle firmware and serial in Home Assistant device information
- Electricity and M-Bus meter serials as sensor attributes
- Diagnostic counters for timeouts, CRC errors and total telegram attempts; disabled
  by default

## Sensors

Sensors are created when their corresponding OBIS field is present and valid:

- Imported and exported energy for tariff 1 and tariff 2
- Current imported and exported power
- Active tariff
- Voltage, current, imported power and exported power per phase
- Power failure, long power failure, voltage sag and voltage swell counters
- Gas consumption when present
- EcoFlow telegram counters as disabled diagnostic sensors

Malformed optional fields are ignored without discarding the rest of the
telegram.

## Installation

### HACS custom repository

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository with category **Integration**.
3. Install **EcoFlow P1 Energy Tracker**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for
   **EcoFlow P1 Energy Tracker**.
6. Enter only the dongle's hostname or IP address. Port 80 is used automatically.

### Manual

Copy `custom_components/ecoflow_p1` into the `custom_components` directory in
your Home Assistant configuration, then restart Home Assistant.

## Polling interval

Open the integration's **Configure** dialog to select an interval from 5 to 300
seconds. Home Assistant's documented minimum polling interval is 5 seconds.

## Known MVP limitations

- No downloadable Home Assistant diagnostics yet
- DSMR CRC text is not independently recalculated; the P1's own
  `crc_error_times` counter is exposed for diagnostics

## License

MIT
