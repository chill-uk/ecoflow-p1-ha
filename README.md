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
- temporarily enable telegram debug mode.

A changed address is probed before it is saved; serial-backed entries cannot be
pointed at a different P1 dongle. Home Assistant's documented minimum polling
interval is 5 seconds.

Telegram debug mode disables the 15-second value-retention grace period. A
telegram with a missing, empty, malformed, or incorrectly unit-labelled required
electricity field is logged together with its CRC result and raw telegram.
Electricity and M-Bus equipment identifiers are redacted from that log. Disable
debug mode after collecting the information needed for troubleshooting.

## License

MIT
