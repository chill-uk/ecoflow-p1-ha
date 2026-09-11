"""Constants for the EcoFlow P1 Energy Tracker integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "ecoflow_p1"

CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_PHASE_MODE: Final = "phase_mode"
CONF_TELEGRAM_DEBUG: Final = "telegram_debug"
CONF_ENCRYPTED_DIAGNOSTIC_CAPTURE: Final = "encrypted_diagnostic_capture"
DEFAULT_POLL_INTERVAL: Final = 5
MIN_POLL_INTERVAL: Final = 5
MAX_POLL_INTERVAL: Final = 300

PHASE_MODE_SINGLE: Final = "single"
PHASE_MODE_THREE: Final = "three"
DEFAULT_PHASE_MODE: Final = PHASE_MODE_SINGLE

API_PATH: Final = "/getdebugdata"
REQUEST_TIMEOUT: Final = 4
TRANSIENT_FAILURE_GRACE_SECONDS: Final = 15

PLATFORMS: Final = [Platform.SENSOR]
