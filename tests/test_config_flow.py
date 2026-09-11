"""Tests for EcoFlow P1 config-flow validation."""

from __future__ import annotations

import sys
import unittest
from types import ModuleType, SimpleNamespace

from .helpers import load_module


def _install_home_assistant_stubs() -> None:
    """Install the small Home Assistant surface used by config_flow."""
    voluptuous = ModuleType("voluptuous")
    voluptuous.Schema = lambda value: value
    voluptuous.Required = lambda key, **_kwargs: key
    voluptuous.All = lambda *validators: validators
    voluptuous.Coerce = lambda value_type: value_type
    voluptuous.Range = lambda **kwargs: kwargs
    sys.modules["voluptuous"] = voluptuous

    homeassistant = sys.modules.setdefault("homeassistant", ModuleType("homeassistant"))
    homeassistant.__path__ = []
    config_entries = ModuleType("homeassistant.config_entries")

    class _Flow:
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)
            cls.domain = domain

        async def async_set_unique_id(self, unique_id):
            self.unique_id = unique_id

        def _abort_if_unique_id_configured(self, updates=None):
            self.unique_id_updates = updates

        def async_create_entry(self, *, title, data):
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(self, *, step_id, data_schema, errors=None):
            return {"type": "form", "step_id": step_id, "errors": errors or {}}

    class _OptionsFlowWithReload(_Flow):
        pass

    config_entries.ConfigFlow = _Flow
    config_entries.ConfigFlowResult = dict
    config_entries.OptionsFlowWithReload = _OptionsFlowWithReload
    sys.modules[config_entries.__name__] = config_entries

    ha_const = ModuleType("homeassistant.const")
    ha_const.CONF_HOST = "host"

    class Platform:
        SENSOR = "sensor"

    ha_const.Platform = Platform
    sys.modules[ha_const.__name__] = ha_const

    core = ModuleType("homeassistant.core")
    core.callback = lambda function: function
    sys.modules[core.__name__] = core

    helpers = ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules[helpers.__name__] = helpers
    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda _hass: object()
    sys.modules[aiohttp_client.__name__] = aiohttp_client
    selector = ModuleType("homeassistant.helpers.selector")

    class _Selector:
        def __init__(self, config=None):
            self.config = config

    class _SelectSelectorConfig:
        def __init__(self, **kwargs):
            self.options = kwargs

    class _SelectSelectorMode:
        DROPDOWN = "dropdown"

    selector.BooleanSelector = _Selector
    selector.SelectSelector = _Selector
    selector.SelectSelectorConfig = _SelectSelectorConfig
    selector.SelectSelectorMode = _SelectSelectorMode
    sys.modules[selector.__name__] = selector
    helpers.selector = selector


_install_home_assistant_stubs()
load_module("custom_components.ecoflow_p1.models")
load_module("custom_components.ecoflow_p1.parser")
load_module("custom_components.ecoflow_p1.api")
constants = sys.modules.get("custom_components.ecoflow_p1.const")
if constants is None:
    constants = load_module("custom_components.ecoflow_p1.const")
constants.CONF_POLL_INTERVAL = "poll_interval"
constants.DEFAULT_POLL_INTERVAL = 5
constants.DOMAIN = "ecoflow_p1"
constants.MAX_POLL_INTERVAL = 300
constants.MIN_POLL_INTERVAL = 5
constants.CONF_PHASE_MODE = "phase_mode"
constants.CONF_TELEGRAM_DEBUG = "telegram_debug"
constants.CONF_ENCRYPTED_DIAGNOSTIC_CAPTURE = "encrypted_diagnostic_capture"
constants.DEFAULT_PHASE_MODE = "single"
constants.PHASE_MODE_SINGLE = "single"
constants.PHASE_MODE_THREE = "three"
config_flow = load_module("custom_components.ecoflow_p1.config_flow")


class FakeApi:
    """Return a prepared device identity to config-flow tests."""

    serial = "P1-123"

    def __init__(self, _session, host):
        self.host = host

    async def async_get_data(self):
        return SimpleNamespace(serial=self.serial)


class FakeConfigEntries:
    """Provide configured entries for duplicate-address checks."""

    def __init__(self, entries=()):
        self.entries = entries

    def async_entries(self, _domain):
        return self.entries


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    """Verify setup and editable-address validation behavior."""

    def test_normalizes_supported_addresses(self) -> None:
        """Accept local host forms and reject URLs with unsupported details."""
        self.assertEqual(config_flow._normalize_host(" P1.LOCAL. "), "p1.local")
        self.assertEqual(
            config_flow._normalize_host("http://192.168.1.4"), "192.168.1.4"
        )
        self.assertEqual(config_flow._normalize_host("2001:db8::1"), "[2001:db8::1]")
        for value in ("https://p1.local", "p1.local:8080", "p1.local/path", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                config_flow._normalize_host(value)

    async def test_user_step_validates_device_and_uses_dongle_serial(self) -> None:
        """Probe /getdebugdata and use the P1 serial as the unique ID."""
        config_flow.EcoFlowP1Api = FakeApi
        flow = config_flow.EcoFlowP1ConfigFlow()
        flow.hass = SimpleNamespace(config_entries=FakeConfigEntries())

        result = await flow.async_step_user({"host": "P1.LOCAL."})

        self.assertEqual(flow.unique_id, "P1-123")
        self.assertEqual(result["data"], {"host": "p1.local"})

    async def test_options_revalidate_and_save_changed_address(self) -> None:
        """Validate an edited address and retain the polling setting."""
        config_flow.EcoFlowP1Api = FakeApi
        flow = config_flow.EcoFlowP1OptionsFlow()
        flow.config_entry = SimpleNamespace(
            entry_id="one",
            unique_id="P1-123",
            data={"host": "old.local"},
            options={"poll_interval": 5},
        )
        flow.hass = SimpleNamespace(config_entries=FakeConfigEntries())

        result = await flow.async_step_init(
            {
                "host": "new.local",
                "poll_interval": 10,
                "phase_mode": "three",
                "telegram_debug": True,
                "encrypted_diagnostic_capture": True,
            }
        )

        self.assertEqual(
            result["data"],
            {
                "host": "new.local",
                "poll_interval": 10,
                "phase_mode": "three",
                "telegram_debug": True,
                "encrypted_diagnostic_capture": True,
            },
        )

    async def test_options_reject_a_different_physical_device(self) -> None:
        """Do not silently repoint a serial-backed entry to another dongle."""
        config_flow.EcoFlowP1Api = FakeApi
        flow = config_flow.EcoFlowP1OptionsFlow()
        flow.config_entry = SimpleNamespace(
            entry_id="one",
            unique_id="P1-other",
            data={"host": "old.local"},
            options={},
        )
        flow.hass = SimpleNamespace(config_entries=FakeConfigEntries())

        result = await flow.async_step_init(
            {
                "host": "new.local",
                "poll_interval": 5,
                "phase_mode": "single",
                "telegram_debug": False,
                "encrypted_diagnostic_capture": False,
            }
        )

        self.assertEqual(result["errors"], {"base": "wrong_device"})


if __name__ == "__main__":
    unittest.main()
