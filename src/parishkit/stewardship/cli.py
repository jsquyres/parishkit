"""Safe scaffold diagnostics using ParishKit's shared argument/YAML helpers."""

import json
import sys
from collections.abc import Sequence
from importlib.metadata import version

from parishkit.cli import parser_with_common_options
from parishkit.config import ConfigError, load_yaml_config


def main(argv: Sequence[str] | None = None) -> int:
    """Report package version or YAML readability without printing its contents.

    Syntax validation is explicitly not deployment readiness. Do not configure
    Django, contact providers, or perform any writes from these diagnostics.
    """
    parser = parser_with_common_options(
        "pk-stewardship", description="Stewardship application diagnostics"
    )
    parser.add_argument("--version", action="store_true")
    parser.add_argument("command", nargs="?", choices=["config-check"])
    args = parser.parse_args(argv)
    if args.version:
        print(f"pk-stewardship {version('parishkit')}")
        return 0
    if args.command is None:
        parser.print_help()
        return 2
    if args.config is None:
        parser.error("config-check requires --config")
    try:
        load_yaml_config(args.config, required=True)
    except (ConfigError, OSError, UnicodeError):
        # YAML parser errors can embed source lines containing secret values.
        print("ERROR: configuration must be a readable YAML mapping", file=sys.stderr)
        return 2
    print(json.dumps({"yaml_mapping_valid": True, "deployment_validated": False}))
    return 0
