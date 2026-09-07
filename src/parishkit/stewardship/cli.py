"""Safe scaffold diagnostics using ParishKit's shared argument/YAML helpers."""

import json
import sys
from collections.abc import Sequence
from importlib.metadata import version

from parishkit.cli import parser_with_common_options
from parishkit.config import ConfigError, load_yaml_config

from .deployment import DeploymentProfile, ServiceRole, load_deployment


def main(argv: Sequence[str] | None = None) -> int:
    """Report package version or YAML readability without printing its contents.

    Syntax validation is explicitly not deployment readiness. Do not configure
    Django, contact providers, or perform any writes from these diagnostics.
    """
    parser = parser_with_common_options(
        "pk-stewardship", description="Stewardship application diagnostics"
    )
    parser.add_argument("--version", action="store_true")
    parser.add_argument(
        "command", nargs="?", choices=["config-check", "validate-deployment"]
    )
    parser.add_argument("--profile", choices=list(DeploymentProfile))
    parser.add_argument("--service-role", choices=list(ServiceRole))
    parser.add_argument("--public-origin")
    parser.add_argument("--runtime-root")
    args = parser.parse_args(argv)
    if args.version:
        print(f"pk-stewardship {version('parishkit')}")
        return 0
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "validate-deployment":
        overrides = {
            key: value
            for key, value in {
                "PARISHKIT_STEWARDSHIP_PROFILE": args.profile,
                "PARISHKIT_STEWARDSHIP_SERVICE_ROLE": args.service_role,
                "PARISHKIT_STEWARDSHIP_PUBLIC_ORIGIN": args.public_origin,
                "PARISHKIT_ROOT": args.runtime_root,
            }.items()
            if value is not None
        }
        try:
            load_deployment(args.config, overrides=overrides)
        except ConfigError:
            print("ERROR: deployment configuration is invalid", file=sys.stderr)
            return 2
        print(json.dumps({"deployment_syntax_valid": True, "startup_validated": False}))
        return 0
    if args.config is None:
        parser.error("config-check requires --config")
    try:
        load_yaml_config(args.config, required=True, reject_duplicate_keys=True)
    except (ConfigError, OSError, UnicodeError):
        # YAML parser errors can embed source lines containing secret values.
        print("ERROR: configuration must be a readable YAML mapping", file=sys.stderr)
        return 2
    print(json.dumps({"yaml_mapping_valid": True, "deployment_validated": False}))
    return 0
