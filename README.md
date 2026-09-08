# EcoFlow P1 Energy Tracker for Home Assistant

A local-only Home Assistant custom integration for the EcoFlow P1 Energy
Tracker. It reads the raw DSMR telegram from the dongle's local
HTTP endpoint:

```text
GET http://<device-ip>/getdebugdata
```

It does **not** use the EcoFlow cloud API.

## Features

- UI configuration by hostname or IP address
- Device identity based on the P1 dongle serial number (`SN`)
- One coordinated HTTP request per update
- Configurable 5–300 second polling interval (5 seconds by default)
- DSMR parsing by OBIS identifier, independent of line order
- Single-phase and three-phase electricity measurements
- Dynamic M-Bus discovery with no fixed channel-number limit
- Gas, water and energy M-Bus readings classified by device type and unit
- DSMR version, meter manufacturer/model and decoded meter serials
- Dongle firmware and serial in Home Assistant device information
- Separate Home Assistant devices for the dongle, electricity meter and each
  M-Bus meter
- Translatable entity names with a quieter default entity selection
- Revalidated, editable device address in the integration options
- Diagnostic counters for timeouts, CRC errors and total telegram attempts; disabled
  by default
- Automated parser, API and config-flow tests

## Sensors

Sensors are created when their corresponding OBIS field is present and valid:

- Imported and exported energy for tariff 1 and tariff 2
- Current imported and exported power
- Active tariff
- Voltage, current, imported power and exported power per phase
- Power failure, long power failure, voltage sag and voltage swell counters
- Gas, water or energy consumption from discovered M-Bus meters
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

Open the integration's **Configure** dialog to change its hostname/IP address or
select an interval from 5 to 300 seconds. A changed address is probed before it
is saved; serial-backed entries cannot be pointed at a different P1 dongle.
Home Assistant's documented minimum polling interval is 5 seconds.

## Known MVP limitations

- No downloadable Home Assistant diagnostics yet
- DSMR CRC text is not independently recalculated; the P1's own
  `crc_error_times` counter is exposed for diagnostics

## License

MIT
