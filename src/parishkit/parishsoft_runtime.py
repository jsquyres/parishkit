"""Runtime helpers for tools that load ParishSoft data."""

from __future__ import annotations

from pathlib import Path

from parishkit.cli import CommonOptions
from parishkit.config import ConfigData, ConfigError
from parishkit.parishsoft import ParishSoftClient, ParishSoftConfig, parse_cache_limit


def parishsoft_client_from_config(
    common: CommonOptions,
    config: ConfigData,
) -> ParishSoftClient:
    parishsoft_config = config.get("parishsoft", {})
    if not isinstance(parishsoft_config, dict):
        raise ConfigError("parishsoft configuration must be a mapping")
    expected_organization = parishsoft_config.get("expected_organization")
    if expected_organization is not None and not isinstance(expected_organization, str):
        raise ConfigError("parishsoft.expected_organization must be a string")
    api_key = Path(common.ps_api_key_file).expanduser().read_text(encoding="utf-8")
    return ParishSoftClient(
        ParishSoftConfig(
            api_key=api_key.strip(),
            cache_dir=Path(common.ps_cache_dir),
            cache_limit=parse_cache_limit(common.ps_cache_limit),
            expected_organization=expected_organization,
        )
    )
