"""Configuration loading and validation for the Second Brain.

Reads settings from config.yaml and environment variables, including
API keys, storage backends, and connector credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StoreConfig:
    type: str
    path: Path
    github_repo: str = ""
    github_token: str = ""


@dataclass
class MicrosoftConfig:
    client_id: str
    tenant_id: str


@dataclass
class Config:
    stores: dict[str, StoreConfig]
    microsoft: MicrosoftConfig


_DEFAULT_PATH = Path.home() / ".config" / "second-brain" / "config.yaml"

_cached_config: Config | None = None


def _parse_stores(raw: dict[str, Any]) -> dict[str, StoreConfig]:
    stores: dict[str, StoreConfig] = {}
    for name, data in raw.items():
        stores[name] = StoreConfig(
            type=data.get("type", "local"),
            path=Path(data.get("path", "")).expanduser(),
            github_repo=data.get("github_repo", ""),
            github_token=data.get("github_token", ""),
        )
    return stores


def load_config(path: Path | None = None) -> Config:
    """Load configuration from YAML and apply environment variable overrides."""
    path = path or _DEFAULT_PATH

    with open(path) as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    # --- stores ---
    stores = _parse_stores(raw.get("stores", {}))
    if token := os.environ.get("SECOND_BRAIN_GITHUB_TOKEN"):
        if "personal" in stores:
            stores["personal"].github_token = token

    # --- microsoft ---
    ms = raw.get("microsoft", {})
    microsoft_cfg = MicrosoftConfig(
        client_id=os.environ.get("SECOND_BRAIN_MS_CLIENT_ID", ms.get("client_id", "")),
        tenant_id=os.environ.get("SECOND_BRAIN_MS_TENANT_ID", ms.get("tenant_id", "")),
    )

    return Config(
        stores=stores,
        microsoft=microsoft_cfg,
    )


def get_config() -> Config:
    """Return a cached singleton of the loaded configuration."""
    global _cached_config
    if _cached_config is None:
        _cached_config = load_config()
    return _cached_config
