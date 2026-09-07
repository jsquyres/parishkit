"""Safe scaffold diagnostics using ParishKit's shared argument/YAML helpers."""

import json
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from parishkit.cli import parser_with_common_options
from parishkit.config import ConfigError, load_yaml_config

from .deployment import DeploymentProfile, ServiceRole, load_deployment
from .services import healthcheck, prepare_development, run_service


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch explicit scaffold commands without disclosing configuration.

    Syntax validation is explicitly not deployment readiness. Do not configure
    Django, contact providers, or perform writes from syntax diagnostics.
    Service execution and new development-tree provisioning are explicit commands.
    """
    parser = parser_with_common_options(
        "pk-stewardship", description="Stewardship application commands"
    )
    parser.add_argument("--version", action="store_true")
    parser.add_argument(
        "command",
        nargs="?",
        choices=[
            "config-check",
            "validate-deployment",
            "service",
            "healthcheck",
            "prepare-development",
        ],
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
    if args.command == "service":
        return run_service(args.profile, args.service_role)
    if args.command == "healthcheck":
        return healthcheck()
    if args.command == "prepare-development":
        if args.runtime_root is None:
            parser.error("prepare-development requires an explicit --runtime-root")
        try:
            prepare_development(Path(args.runtime_root).absolute())
        except OSError:
            print(
                "ERROR: use a new writable runtime directory with an existing parent; "
                "no existing data was replaced",
                file=sys.stderr,
            )
            return 2
        print("Created local scaffold storage; application bootstrap is still required")
        return 0
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
