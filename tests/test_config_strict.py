"""Opt-in strict YAML parsing without changing existing CLI configuration."""

from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest

from parishkit import config
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


def test_strict_byte_limit_counts_encoded_bytes(tmp_path, monkeypatch):
    """Exact byte ceilings are accepted; one extra UTF-8 byte fails before YAML."""
    path = tmp_path / "synthetic-private-path.yaml"
    text = "key: café\n"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(config, "STRICT_YAML_MAX_BYTES", len(text.encode("utf-8")))
    assert load_yaml_config(path, reject_duplicate_keys=True) == {"key": "café"}
    monkeypatch.setattr(config, "STRICT_YAML_MAX_BYTES", len(text.encode("utf-8")) - 1)
    with pytest.raises(
        ConfigError, match="^configuration YAML exceeds input byte limit$"
    ):
        load_yaml_config(path, reject_duplicate_keys=True)
    assert load_yaml_config(path) == {"key": "café"}


def test_strict_read_never_requests_more_than_limit_plus_one(tmp_path, monkeypatch):
    """File growth after a stat cannot turn the strict read into an unbounded read."""
    path = tmp_path / "configuration.yaml"
    path.touch()
    monkeypatch.setattr(config, "STRICT_YAML_MAX_BYTES", 16)
    stream = BytesIO(b"x" * 100)
    read = Mock(wraps=stream.read)
    monkeypatch.setattr(stream, "read", read)
    monkeypatch.setattr(Path, "open", Mock(return_value=stream))
    with pytest.raises(ConfigError, match="input byte limit"):
        load_yaml_config(path, reject_duplicate_keys=True)
    read.assert_called_once_with(17)
    assert stream.closed


@pytest.mark.parametrize(
    ("limit", "ceiling", "text", "expected"),
    [
        ("STRICT_YAML_MAX_NODES", 5, "items: [1, 2]", {"items": [1, 2]}),
        ("STRICT_YAML_MAX_DEPTH", 4, "items: [[value]]", {"items": [["value"]]}),
    ],
)
def test_strict_structural_limit_boundaries(
    tmp_path, monkeypatch, limit, ceiling, text, expected
):
    """Both ceilings are inclusive, reset per read, and leave legacy reads alone."""
    path = tmp_path / "configuration.yaml"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(config, limit, ceiling)
    for _ in range(2):
        assert load_yaml_config(path, reject_duplicate_keys=True) == expected
    monkeypatch.setattr(config, limit, ceiling - 1)
    with pytest.raises(ConfigError, match="structural limits"):
        load_yaml_config(path, reject_duplicate_keys=True)
    assert load_yaml_config(path) == expected


@pytest.mark.parametrize("merge", [False, True])
def test_alias_expansion_is_bounded_before_construction(monkeypatch, merge):
    """Compact alias DAGs cannot cause unbounded merge or value expansion."""
    monkeypatch.setattr(config, "STRICT_YAML_MAX_NODES", 100)
    text = "v0: &a0 {key: value}\n" if merge else "v0: &a0 [value]\n"
    for index in range(1, 9):
        references = f"[*a{index - 1}, *a{index - 1}]"
        value = "{<<: " + references + "}" if merge else references
        text += f"v{index}: &a{index} {value}\n"
    construct = Mock(side_effect=AssertionError("construction must not begin"))
    monkeypatch.setattr(config._UniqueKeySafeLoader, "construct_mapping", construct)
    loader = config._UniqueKeySafeLoader(text)
    try:
        with pytest.raises(ConfigError, match="structural limits"):
            loader.get_single_data()
        assert loader._parse_nodes <= 100
        assert loader._expanded_nodes == 101
        construct.assert_not_called()
    finally:
        loader.dispose()


@pytest.mark.parametrize(
    "text",
    [
        "value: &cycle [*cycle]",
        "value: &cycle {<<: *cycle}",
        "".join("  " * depth + "key:\n" for depth in range(550)),
        "v0: &a0 [value]\n"
        + "".join(f"v{index}: &a{index} [*a{index - 1}]\n" for index in range(1, 70)),
    ],
    ids=["sequence-cycle", "merge-cycle", "deep-mapping", "deep-alias-chain"],
)
def test_strict_depth_and_cycles_fail_safely(tmp_path, text):
    """Both syntactic and alias-expanded nesting stop before unsafe recursion."""
    path = tmp_path / "synthetic-private-path.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(
        ConfigError, match="^configuration YAML exceeds structural limits$"
    ):
        load_yaml_config(path, reject_duplicate_keys=True)


def test_small_aliases_and_unambiguous_merges_remain_supported(tmp_path):
    """Bounds do not turn ordinary safe YAML reuse into an unsupported feature."""
    path = tmp_path / "configuration.yaml"
    path.write_text(
        "base: &base {first: one}\ncopy: *base\nmerged: {<<: *base, second: two}\n",
        encoding="utf-8",
    )
    assert load_yaml_config(path, reject_duplicate_keys=True) == {
        "base": {"first": "one"},
        "copy": {"first": "one"},
        "merged": {"first": "one", "second": "two"},
    }


def test_unexpected_parser_recursion_is_normalized_only_for_strict_reads(
    tmp_path, monkeypatch
):
    """Defense in depth hides raw recursion text without changing legacy errors."""
    path = tmp_path / "synthetic-private-path.yaml"
    path.write_text("key: value", encoding="utf-8")
    monkeypatch.setattr(
        config.yaml, "load", Mock(side_effect=RecursionError("synthetic-secret"))
    )
    with pytest.raises(
        ConfigError, match="^configuration YAML cannot be safely parsed$"
    ) as exc:
        load_yaml_config(path, reject_duplicate_keys=True)
    assert exc.value.__suppress_context__
    with pytest.raises(RecursionError, match="synthetic-secret"):
        load_yaml_config(path)


def test_strict_invalid_utf8_is_normalized(tmp_path):
    """An invalid byte sequence has the same sanitized strict parsing boundary."""
    path = tmp_path / "synthetic-private-path.yaml"
    path.write_bytes(b"\xff")
    with pytest.raises(
        ConfigError, match="^configuration YAML cannot be safely parsed$"
    ):
        load_yaml_config(path, reject_duplicate_keys=True)
