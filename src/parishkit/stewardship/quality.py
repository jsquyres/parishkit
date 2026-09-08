"""Developer-only scoped coverage runner; no provider or deployment operations."""

import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .arguments import StewardshipArgumentParser

PACKAGE = "src/parishkit/stewardship"
FLOOR = 80


@dataclass(frozen=True)
class CoverageScope:
    """Validated import targets plus every file required in the coverage report."""

    modules: tuple[str, ...]
    files: frozenset[str]


def load_scope(root: Path) -> CoverageScope:
    """Require the whole package and exact, unique in-repository shared modules."""
    root = root.resolve(strict=True)
    with (root / "coverage-stewardship.toml").open("rb") as stream:
        manifest = tomllib.load(stream)
    if set(manifest) != {"schema_version", "shared_modules"}:
        raise ValueError("coverage manifest has unknown or missing fields")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("unsupported coverage manifest version")
    shared = manifest["shared_modules"]
    if not isinstance(shared, list):
        raise ValueError("shared_modules must be a list")
    package = root / PACKAGE
    if not (package / "__init__.py").is_file():
        raise ValueError("the stewardship package is required")
    names = [path.relative_to(root).as_posix() for path in package.rglob("*.py")]
    for name in shared:
        if (
            not isinstance(name, str)
            or not name.startswith("src/parishkit/")
            or name.startswith(PACKAGE + "/")
        ):
            raise ValueError("shared coverage paths must name shared ParishKit modules")
        names.append(name)
    seen = set()
    for name in names:
        path = PurePosixPath(name)
        target = root / path
        if (
            path.as_posix() != name
            or ".." in path.parts
            or "\\" in name
            or path.suffix != ".py"
            or not target.is_file()
            or target.resolve() != target
            or not target.resolve().is_relative_to(root)
            or name in seen
        ):
            raise ValueError(
                "coverage paths must be unique, real repository Python files"
            )
        seen.add(name)
    modules = ("parishkit.stewardship",) + tuple(
        ".".join(PurePosixPath(name).with_suffix("").parts[1:]) for name in shared
    )
    return CoverageScope(modules, frozenset(seen))


def coverage_percentages(
    root: Path, scope: CoverageScope, report: Path
) -> tuple[float, float]:
    """Validate branch-enabled JSON and calculate independent unrounded totals.

    Missing scoped files fail rather than silently improving the denominator.
    Report-wide blended percentages and unrelated files never affect the gate.
    """
    data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("meta", {}).get("branch_coverage") is not True:
        raise ValueError("coverage must measure branches")
    files = {}
    for name, details in data["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError("coverage report references files outside the repository")
        canonical = path.relative_to(root).as_posix()
        if canonical in files:
            raise ValueError("coverage report contains duplicate file aliases")
        files[canonical] = details
    if not scope.files <= files.keys():
        raise ValueError("coverage report is missing scoped files")
    totals = [0, 0, 0, 0]
    for name in scope.files:
        summary = files[name]["summary"]
        values = [
            summary[key]
            for key in (
                "covered_lines",
                "num_statements",
                "covered_branches",
                "num_branches",
            )
        ]
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("coverage counts must be nonnegative integers")
        if values[0] > values[1] or values[2] > values[3]:
            raise ValueError("covered counts cannot exceed totals")
        totals = [left + right for left, right in zip(totals, values, strict=True)]
    return (
        100 * totals[0] / totals[1] if totals[1] else 100.0,
        100 * totals[2] / totals[3] if totals[3] else 100.0,
    )


def main(argv=None) -> int:
    """Run the full baseline with manifest-derived sources, then enforce floors."""
    parser = StewardshipArgumentParser(
        "python -m parishkit.stewardship.quality",
        description="Run credential-free tests with stewardship coverage gates",
        error_hints={
            "--repository-root": "--repository-root requires a path (value redacted)",
            "--report": "--report requires a file path (value redacted)",
        },
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, help="required coverage report path")
    args = parser.parse_args(argv)
    if args.report is None:
        parser.usage_error("--report is required")
    try:
        root = args.repository_root.resolve(strict=True)
        scope = load_scope(root)
        report = args.report.absolute()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--cov-branch",
                *(f"--cov={module}" for module in scope.modules),
                f"--cov-report=json:{report}",
                "--cov-report=term",
                "-p",
                "no:cacheprovider",
            ],
            cwd=root,
            check=False,
        )
        if result.returncode:
            return result.returncode
        lines, branches = coverage_percentages(root, scope, report)
    except (OSError, ValueError, KeyError, TypeError):
        print("ERROR: invalid coverage manifest or report", file=sys.stderr)
        return 2
    print(f"Stewardship scope: lines {lines:.2f}%; branches {branches:.2f}%")
    return 0 if lines >= FLOOR and branches >= FLOOR else 1


if __name__ == "__main__":
    raise SystemExit(main())
