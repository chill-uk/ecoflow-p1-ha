"""Helpers for testing integration modules without installing Home Assistant."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "ecoflow_p1"


def load_module(module_name: str):
    """Load an integration module while bypassing the package __init__."""
    if module_name in sys.modules:
        return sys.modules[module_name]

    custom_components = sys.modules.setdefault(
        "custom_components", types.ModuleType("custom_components")
    )
    custom_components.__path__ = [str(ROOT / "custom_components")]
    package = sys.modules.setdefault(
        "custom_components.ecoflow_p1", types.ModuleType("custom_components.ecoflow_p1")
    )
    package.__path__ = [str(INTEGRATION)]

    short_name = module_name.rsplit(".", 1)[-1]
    spec = importlib.util.spec_from_file_location(
        module_name, INTEGRATION / f"{short_name}.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
