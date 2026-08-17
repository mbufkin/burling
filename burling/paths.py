"""Resolve harness folders relative to this package, not the caller's cwd."""

from __future__ import annotations

from pathlib import Path

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
CONFIG_PATH = PACKAGE_DIR / "config.yaml"
EXAMPLE_CONFIG_PATH = PACKAGE_DIR / "config.example.yaml"


def load_config(path: Path | None = None) -> dict:
    """Load YAML config. Prefer a local config.yaml; fall back to the example.

    Best practice: ship a generic example in git, keep machine-specific
    overrides (rclone remotes, model names) in an untracked config.yaml.
    """
    if path is not None:
        cfg_path = path
    elif CONFIG_PATH.is_file():
        cfg_path = CONFIG_PATH
    else:
        cfg_path = EXAMPLE_CONFIG_PATH
    if not cfg_path.is_file():
        raise FileNotFoundError(
            f"No config at {cfg_path}. Copy {EXAMPLE_CONFIG_PATH.name} to config.yaml."
        )
    with cfg_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def intake_dir(cfg: dict) -> Path:
    raw = Path(cfg["paths"]["intake_dir"])
    return raw if raw.is_absolute() else PACKAGE_DIR / raw


def output_dir(cfg: dict) -> Path:
    raw = Path(cfg["paths"]["output_dir"])
    return raw if raw.is_absolute() else PACKAGE_DIR / raw
