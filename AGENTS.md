# AI-assisted contribution guide

This file provides repository context for coding assistants and contributors using
AI-generated changes. Read it before editing the project. Existing code, tests, and
CI workflows remain the source of truth when they differ from a suggestion here.

## Project purpose

EcoFlow P1 is a local-only Home Assistant custom integration. It polls the
unauthenticated local endpoint `GET /getdebugdata`, extracts the raw DSMR telegram
from the JSON `debugdata` field, validates it, and maps supported OBIS values to
Home Assistant entities.

- Never add or use the EcoFlow cloud API.
- Use Home Assistant's asynchronous aiohttp client; do not add blocking HTTP calls.
- Preserve temporary network-failure handling and the 15-second value-retention
  grace period.
- Debug logging and encrypted diagnostic capture are separate features. Do not log
  unredacted meter or M-Bus identifiers.

## Repository layout

- `custom_components/ecoflow_p1/`: integration implementation.
- `custom_components/ecoflow_p1/strings.json`: canonical English UI and entity
  strings used by Home Assistant.
- `custom_components/ecoflow_p1/translations/en.json`: English translation copy.
- `tests/`: unit tests and DSMR fixtures.
- `.github/workflows/tests.yml`: Python 3.14 unit-test workflow.
- `.github/workflows/validate.yml`: Ruff, hassfest, and HACS validation.

## Required checks

Use Python 3.14 when possible. A minimal local environment can be created with:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install aiohttp pynacl ruff
```

Run these commands before presenting or pushing a change:

```bash
ruff format custom_components tests
ruff check custom_components tests
ruff format --check custom_components tests
python -m unittest discover
```

`ruff format --check` only reports formatting problems. Run `ruff format` first to
fix them. Ruff uses an 88-character line length and the lint rules configured in
`pyproject.toml`. Do not hand-format code in a way that conflicts with Ruff.

Do not claim that a change passes unless all applicable commands have completed
successfully. If a command cannot be run, state that clearly in the hand-off.

## Home Assistant entity conventions

- Define entity names with `translation_key`; do not pass `name=` to
  `EcoFlowP1SensorDescription`.
- Add every new translation key to both `strings.json` and
  `translations/en.json`.
- Reuse the existing `_energy()`, `_power()`, and `_count()` helpers where they fit.
- Telegram power values normally arrive in `kW`, but power entities in this
  integration are exposed natively and preferentially in `W`. Use the existing
  `_power()` helper or apply its `Decimal(1000)` multiplier in custom value paths.
- Use `Decimal` while parsing and converting meter measurements. Avoid binary
  floating-point conversion for entity states.
- Give numeric sensors the appropriate Home Assistant device class, native unit,
  and state class.
- Keep one meaningful scalar value as an entity's state. Do not encode lists or
  records as comma-separated strings. Put small structured datasets in attributes,
  or model them as separate stable entities when that is genuinely useful.
- Optional, diagnostic, regional, and phase-specific entities should have sensible
  default enablement. L2 and L3 entities remain disabled by default for a
  single-phase setup.
- Keep released unique IDs stable. If an entity key must change, add an entity
  registry migration rather than silently creating a replacement entity.
- Link child devices with `via_device_id`, not the deprecated `via_device` field.

Example power description:

```python
_power(
    "current_average_demand",
    "1-0:1.4.0",
    enabled=False,
)
```

If a custom parser extracts the value instead of the generic OBIS value path, it
must still apply the entity description's multiplier:

```python
return (
    value * description.value_multiplier
    if value is not None
    else None
)
```

## DSMR and OBIS parsing

- Parse by OBIS identifier, never by fixed line number or telegram position.
- Tolerate CRLF, blank lines, unknown fields, missing optional values, different
  DSMR variants, absent M-Bus devices, and single- or three-phase meters.
- Validate units before accepting a measurement.
- A malformed optional OBIS value must not invalidate the entire telegram.
- Preserve CRC validation and framing checks.
- Treat timestamps ending in `S` or `W` as DSMR local timestamps with summer- or
  winter-time information. Invalid placeholder timestamps must not crash parsing.
- M-Bus channels are discovered dynamically; do not reintroduce a fixed channel
  limit.
- When adding a regional OBIS variant, confirm its shape against an official
  specification or multiple real, redacted telegrams.

## Tests for parser and sensor changes

Every parsing or entity change should include focused tests. Use realistic redacted
telegram fixtures and cover, where relevant:

- the normal valid value;
- missing optional fields;
- empty or malformed values;
- unexpected units;
- alternate OBIS variants;
- variable-length repeating groups;
- invalid timestamp placeholders;
- correct Home Assistant native units and multipliers;
- translation-key use and default entity enablement;
- stable unique IDs or migrations.

Tests should assert the parsed value, unit, timestamp, attributes, and entity
metadata rather than merely confirming that parsing did not raise an exception.

## Scope and releases

- Keep changes focused on the issue or request being addressed.
- Do not update the manifest version, create tags, publish releases, or modify
  release notes unless explicitly requested by the maintainer.
- Do not add new dependencies when a small implementation or an existing project
  dependency is sufficient.
- Preserve unrelated README and contributor changes when synchronizing branches.

## Before handing off a change

Confirm all of the following:

- The implementation matches a real DSMR/OBIS structure.
- Entity states, units, attributes, translations, and defaults follow Home
  Assistant conventions.
- New behavior has tests, including malformed and missing input where appropriate.
- `ruff format`, `ruff check`, `ruff format --check`, and unit tests pass.
- The diff contains no unrelated files, version bump, tag, release, secret, private
  key, unredacted diagnostic telegram, or serial number.
