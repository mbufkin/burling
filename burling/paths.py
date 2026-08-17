"""Resolve harness folders relative to this package, not the caller's cwd."""

from __future__ import annotations

from pathlib import Path

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
CONFIG_PATH = PACKAGE_DIR / "config.yaml"


def load_config(path: Path | None = None) -> dict:
    cfg_path = path or CONFIG_PATH
    with cfg_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def intake_dir(cfg: dict) -> Path:
    raw = Path(cfg["paths"]["intake_dir"])
    return raw if raw.is_absolute() else PACKAGE_DIR / raw


def output_dir(cfg: dict) -> Path:
    raw = Path(cfg["paths"]["output_dir"])
    return raw if raw.is_absolute() else PACKAGE_DIR / raw
