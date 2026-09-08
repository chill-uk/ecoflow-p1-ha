"""Config flow for the EcoFlow P1 Energy Tracker integration."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    EcoFlowP1Api,
    EcoFlowP1ConnectionError,
    EcoFlowP1ResponseError,
)
from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)


class EcoFlowP1ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an EcoFlow P1 config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Configure an EcoFlow P1 using its hostname or IP address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                host = _normalize_host(user_input[CONF_HOST])
            except ValueError:
                errors["base"] = "invalid_host"
            else:
                api = EcoFlowP1Api(async_get_clientsession(self.hass), host)
                try:
                    data = await api.async_get_data()
                except EcoFlowP1ConnectionError:
                    errors["base"] = "cannot_connect"
                except EcoFlowP1ResponseError:
                    errors["base"] = "invalid_response"
                else:
                    unique_id = data.serial or f"host:{host.casefold()}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                    return self.async_create_entry(
                        title=data.serial or host,
                        data={CONF_HOST: host},
                    )

        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> EcoFlowP1OptionsFlow:
        """Return the options flow."""
        return EcoFlowP1OptionsFlow()


class EcoFlowP1OptionsFlow(OptionsFlow):
    """Handle EcoFlow P1 options."""

    async def async_step_init(
        self, user_input: dict[str, int] | None = None
    ) -> ConfigFlowResult:
        """Configure the polling interval."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_POLL_INTERVAL, default=current): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _normalize_host(value: str) -> str:
    """Normalize a hostname, IPv4 address, or IPv6 address for an HTTP URL."""
    candidate = value.strip()
    if not candidate:
        raise ValueError("Host is empty")

    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    if parsed.scheme and parsed.scheme.casefold() != "http":
        raise ValueError("Only local HTTP is supported")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Enter only a hostname or IP address")
    if parsed.port not in (None, 80):
        raise ValueError("EcoFlow P1 uses port 80")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid host")

    hostname = parsed.hostname.rstrip(".").casefold()
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if any(not label or len(label) > 63 for label in hostname.split(".")):
            raise ValueError("Invalid hostname") from None
        if any(
            not all(char.isalnum() or char == "-" for char in label)
            or label.startswith("-")
            or label.endswith("-")
            for label in hostname.split(".")
        ):
            raise ValueError("Invalid hostname") from None
        return hostname

    return f"[{address.compressed}]" if address.version == 6 else address.compressed
