"""Opt-in strict YAML parsing without changing existing CLI configuration."""

import pytest

from parishkit.config import ConfigError, load_yaml_config


def test_strict_keys_preserve_legacy_default(tmp_path):
    """Strict consumers reject duplicates; legacy consumers keep the last value."""
    path = tmp_path / "configuration.yaml"
    path.write_text("section:\n  value: first\n  value: second\n", encoding="utf-8")
    assert load_yaml_config(path) == {"section": {"value": "second"}}
    with pytest.raises(ConfigError, match="duplicate mapping key"):
        load_yaml_config(path, reject_duplicate_keys=True)


def test_strict_keys_reject_ambiguous_merge_and_unhashable_keys(tmp_path):
    """No nested YAML mapping may silently override an already defined key."""
    path = tmp_path / "configuration.yaml"
    for text in (
        "defaults: &d {value: first}\nsection: {<<: *d, value: second}\n",
        "? [a, b]\n: value\n",
    ):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ConfigError):
            load_yaml_config(path, reject_duplicate_keys=True)
