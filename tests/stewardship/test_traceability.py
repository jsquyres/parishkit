"""Keep specification headings, work packages, and scenario ownership in sync."""

import ast
import re
from pathlib import Path

from parishkit.config import load_yaml_config

ROOT = Path(__file__).resolve().parents[2]
SPECS = ROOT / "docs/specs/stewardship"
PLANS = ROOT / "docs/plans/stewardship"


def specification_headings(path):
    """Extract section headings outside fenced examples, retaining nested scope."""
    headings = []
    fence = None
    for line in path.read_text().splitlines():
        if line.startswith(("```", "~~~")):
            marker = line[:3]
            fence = None if fence == marker else marker if fence is None else fence
        elif fence is None and re.match(r"^#{2,6} ", line):
            headings.append(line.split(" ", 1)[1])
    return headings


def test_every_spec_section_package_and_scenario_has_an_owner():
    """New requirements cannot silently bypass the maintained acceptance map."""
    manifest = load_yaml_config(
        ROOT / "docs/development/stewardship-acceptance.yaml",
        required=True,
        reject_duplicate_keys=True,
    )
    assert manifest["schema_version"] == 1
    packages = set()
    for plan in PLANS.glob("*.md"):
        packages.update(
            re.findall(r"^### ([A-Z]+-\d{2}):", plan.read_text(), re.MULTILINE)
        )
    assert len(packages) == 69
    specs = {
        path.relative_to(SPECS).as_posix(): path for path in SPECS.rglob("spec.md")
    }
    assert set(manifest["sections"]) == specs.keys()
    owned = set()
    for name, path in specs.items():
        headings = specification_headings(path)
        assert len(headings) == len(set(headings)), (
            "disambiguate duplicate section titles"
        )
        mappings = manifest["sections"][name]
        assert mappings.keys() == set(headings), name
        for owners in mappings.values():
            assert owners and len(owners) == len(set(owners))
            assert set(owners) <= packages
            owned.update(owners)
    assert owned == packages
    operations = (SPECS / "operations/spec.md").read_text()
    scenarios = operations.split("## Acceptance scenarios\n", 1)[1].split("\n## ", 1)[0]
    numbers = {
        int(value) for value in re.findall(r"^(\d+)\. ", scenarios, re.MULTILINE)
    }
    assert manifest["scenarios"].keys() == numbers
    for scenario in manifest["scenarios"].values():
        assert scenario["owners"] and set(scenario["owners"]) <= packages
        assert scenario["status"] in {"planned", "partial", "complete"}
        tests = scenario["tests"]
        assert isinstance(tests, list) and len(tests) == len(set(tests))
        assert bool(tests) == (scenario["status"] != "planned")
        for node in tests:
            path_text, function = node.split("::", 1)
            path = ROOT / path_text
            assert path_text.startswith("tests/") and path.resolve().is_relative_to(
                ROOT
            )
            assert path.suffix == ".py" and path.is_file()
            names = {
                item.name
                for item in ast.walk(ast.parse(path.read_text()))
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            assert function in names, node
