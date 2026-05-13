"""
Configuration loader for Helios-X v2.

Loads YAML configs with deep-merge support for ablation overrides.
Reads API secrets from secrets.yaml, .env.local, or environment variables.
"""

import os
import copy
from pathlib import Path

import yaml


# Project root: helios_x_v2/
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override dict into base dict. Override values take precedence."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _parse_env_local(path: Path) -> dict:
    """
    Parse .env.local file with non-standard formatting.
    Handles formats like: 'NREL API_KEY=value,' and 'OpenAQ API_KEY=value'
    """
    secrets = {}
    if not path.exists():
        return secrets

    text = path.read_text(encoding="utf-8")
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue
        key_part, value = line.split("=", 1)
        value = value.strip().strip(",").strip('"').strip("'")

        key_lower = key_part.strip().lower().replace(" ", "_")
        if "nrel" in key_lower:
            secrets["nrel_api_key"] = value
        elif "openaq" in key_lower:
            secrets["openaq_api_key"] = value

    return secrets


def load_secrets() -> dict:
    """Load API secrets. Priority: env vars > secrets.yaml > .env.local"""
    secrets = {}

    env_local = PROJECT_ROOT.parent / ".env.local"
    secrets.update(_parse_env_local(env_local))

    secrets_yaml = CONFIG_DIR / "secrets.yaml"
    if secrets_yaml.exists():
        with open(secrets_yaml, "r") as f:
            yaml_secrets = yaml.safe_load(f) or {}
        secrets.update(yaml_secrets)

    if os.environ.get("NREL_API_KEY"):
        secrets["nrel_api_key"] = os.environ["NREL_API_KEY"]
    if os.environ.get("OPENAQ_API_KEY"):
        secrets["openaq_api_key"] = os.environ["OPENAQ_API_KEY"]

    return secrets


def load_cities() -> dict:
    """Load city definitions from cities.yaml."""
    cities_path = CONFIG_DIR / "cities.yaml"
    with open(cities_path, "r") as f:
        data = yaml.safe_load(f)
    return data["cities"]


def get_config(config_path: str = None, overrides: dict = None) -> dict:
    """
    Load full configuration.

    Args:
        config_path: Path to config YAML. If not default.yaml, it is deep-merged
                     on top of default.yaml (ablation configs only specify deltas).
        overrides: Additional dict overrides applied last.

    Returns:
        Complete configuration dict with 'secrets' and 'cities' keys added.
    """
    default_path = CONFIG_DIR / "default.yaml"

    with open(default_path, "r") as f:
        config = yaml.safe_load(f)

    if config_path:
        config_path = Path(config_path)
        if config_path.resolve() != default_path.resolve():
            with open(config_path, "r") as f:
                override_config = yaml.safe_load(f) or {}
            config = deep_merge(config, override_config)

    if overrides:
        config = deep_merge(config, overrides)

    config["secrets"] = load_secrets()
    config["cities"] = load_cities()

    config["paths"] = {
        "project_root": str(PROJECT_ROOT),
        "config_dir": str(CONFIG_DIR),
        "data_dir": str(DATA_DIR),
        "raw_dir": str(DATA_DIR / "raw"),
        "processed_dir": str(DATA_DIR / "processed"),
        "validation_dir": str(DATA_DIR / "validation"),
        "checkpoints_dir": str(PROJECT_ROOT / "checkpoints"),
        "results_dir": str(PROJECT_ROOT / "results"),
    }

    return config
