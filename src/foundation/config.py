from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing configuration file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"Expected mapping in {path}")
    return data


def definitions() -> dict[str, Any]:
    return load_yaml("definitions.yml")


def sources() -> dict[str, Any]:
    return load_yaml("sources.yml")


def indicators() -> dict[str, Any]:
    return load_yaml("indicators.yml")


def weights() -> dict[str, Any]:
    return load_yaml("weights.yml")


load_definitions = definitions
load_sources = sources
load_indicators = indicators
