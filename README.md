# EcoFlow P1 Energy Tracker for Home Assistant

[![GitHub release](https://img.shields.io/github/release/chill-uk/ecoflow-p1-ha?include_prereleases=&sort=semver&color=blue)](https://github.com/chill-uk/ecoflow-p1-ha/releases/)
[![issues - ecoflow-p1-ha](https://img.shields.io/github/issues/chill-uk/ecoflow-p1-ha)](https://github.com/chill-uk/ecoflow-p1-ha/issues)
[![GH-code-size](https://img.shields.io/github/languages/code-size/chill-uk/ecoflow-p1-ha?color=red)](https://github.com/chill-uk/ecoflow-p1-ha)
[![GH-last-commit](https://img.shields.io/github/last-commit/chill-uk/ecoflow-p1-ha?style=flat-square)](https://github.com/chill-uk/ecoflow-p1-ha/commits/main)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validation](https://github.com/chill-uk/ecoflow-p1-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/chill-uk/ecoflow-p1-ha/actions/workflows/validate.yml)
![GitHub Downloads](https://img.shields.io/github/downloads/chill-uk/ecoflow-p1-ha/total)

A local-only Home Assistant custom integration for the EcoFlow P1 Energy Tracker. It reads the raw DSMR telegram from the dongle's local
HTTP endpoint.

It does **not** use the EcoFlow cloud API.

> [!IMPORTANT]
> This is an unofficial community integration. It is not affiliated with,
> endorsed by, connected with, or supported by EcoFlow.

# Installation

### HACS installation

The quickest way to install this integration is via [HACS](https://github.com/hacs/integration) by clicking the button below:

[![Add to HACS via My Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=chill-uk&repository=ecoflow-p1-ha&category=integration)

1. Click the button above to add this repository to HACS as a custom integration.
2. Install `EcoFlow P1 Energy Tracker` from HACS.
3. Restart Home Assistant.
4. In Home Assistant, go to `Settings -> Devices & Services`.
5. Add the `EcoFlow P1 Energy Tracker` integration.

### Manual installation

1. Copy `custom_components/ecoflow_p1` into your Home Assistant config directory.
2. Restart Home Assistant.
3. In Home Assistant, add the `EcoFlow P1 Energy Tracker` integration from `Settings -> Devices & Services`.

## Polling interval

Open the integration's **Configure** dialog to:

- change its hostname or IP address;
- select a polling interval from 5 to 300 seconds;
- select single-phase or three-phase validation;
- temporarily enable telegram debug mode;
- enable encrypted diagnostic capture for support.

A changed address is probed before it is saved

## Debug mode

Telegram debug mode changes logging only; it does not change entity availability
or disable the 15-second value-retention grace period. 
- Transient HTTP and response failures are logged immediately.
- A telegram with a missing, empty, malformed, or incorrectly labelled field is logged together with its CRC result and telegram.
- Electricity and M-Bus equipment identifiers are redacted from that log.

Disable debug mode after collecting the information needed for troubleshooting.

## Encrypted diagnostic capture

Encrypted diagnostic capture is separate from telegram debug logging. When enabled,
the integration encrypts each polling result immediately with the project's support
public key and retains only ciphertext in memory. No raw telegram is written to
disk or to `home-assistant.log`.

A capture stops automatically after 10 minutes or 120 records. It includes valid
frames, frames rejected by CRC or parsing, required-field validation results, and
request failures. To collect a support bundle:

1. Open the integration's **Configure** dialog.
2. Enable **Encrypted diagnostic capture** and save.
3. Reproduce the problem or wait for the capture to complete.
4. Use the integration menu's **Download diagnostics** action.
5. Disable capture after downloading the file.

Download the diagnostics before disabling the option, reloading the integration,
restarting Home Assistant, or removing the integration. 
Those actions discard the in-memory capture. 

The downloaded file exposes only general version, phase, capture,
and encryption metadata. Raw telegrams and their equipment identifiers are inside
the encrypted records and can only be read with the matching private key.

## Workflow

1. Poll `http://<device-ip>/getdebugdata` at the configured interval.
2. Check the HTTP response and parse its JSON.
3. Extract the raw DSMR telegram from debugdata.
4. Validate the telegram’s CRC.
5. Parse the telegram by OBIS identifier.
6. Validate the required OBIS fields according to the manually selected single-phase or three-phase mode.
7. Convert valid measurements into Home Assistant coordinator data.
8. Update the entities while retaining previous values for optional fields that were not present in this particular telegram.
9. When a frame is invalid:
    * Debug mode enabled: immediately log the reason and redacted raw telegram, with no grace period.
    * Debug mode disabled: preserve the last valid values for up to 15 seconds; if valid data does not return, the affected entities become unavailable.

The log can distinguish between:

* HTTP or JSON failures
* Missing debugdata
* Invalid CRC
* Missing required OBIS fields
* Empty OBIS values
* Malformed values
* Unexpected units

## License

MIT
