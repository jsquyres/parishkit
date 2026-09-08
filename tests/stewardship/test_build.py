"""Credential-free contracts for matching host, CI, and image build tools."""

from pathlib import Path

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[2]
INSTALL_COMMANDS = [
    "python -m pip install -r requirements/stewardship-build.txt",
    "python -m pip install --no-build-isolation -r requirements.txt",
]


def locked_requirements(name):
    """Read generated requirement pins, ignoring only comments and blank lines."""
    requirements = {}
    for line in (ROOT / "requirements" / name).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            requirement = Requirement(line)
            requirements[canonicalize_name(requirement.name)] = requirement
    return requirements


@pytest.mark.parametrize(
    ("workflow", "job"),
    [
        ("ci.yml", "validate"),
        ("ci.yml", "stewardship-compose"),
        ("release.yml", "validate-build"),
    ],
)
def test_ci_installs_locked_backend_before_editable_project(workflow, job):
    """Each host job uses the locked backend rather than fresh isolated resolution."""
    definition = yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text())
    install = next(
        step
        for step in definition["jobs"][job]["steps"]
        if step.get("name") == "Install dependencies"
    )
    assert install["run"].strip().splitlines() == INSTALL_COMMANDS


def test_release_build_uses_installed_locked_tools():
    """Packaging cannot silently resolve a second, unpinned backend after tests."""
    definition = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    build = next(
        step
        for step in definition["jobs"]["validate-build"]["steps"]
        if step.get("name") == "Build artifacts"
    )
    assert build["run"] == "python -m build --no-isolation"
    assert "build" in locked_requirements("stewardship.txt")


def test_build_lock_is_pinned_and_compatible_with_runtime_lock():
    """Installing runtime tools cannot replace shared build dependencies with drift."""
    build = locked_requirements("stewardship-build.txt")
    runtime = locked_requirements("stewardship.txt")
    assert {"hatchling", "editables"} <= build.keys()
    for name, requirement in build.items():
        pins = list(requirement.specifier)
        assert len(pins) == 1 and pins[0].operator == "=="
        assert "*" not in pins[0].version
        if name in runtime:
            assert requirement.specifier == runtime[name].specifier


def test_docker_and_checkout_share_build_lock():
    """The Docker install remains the same locked, non-isolated build approach."""
    dockerfile = (ROOT / "deploy/stewardship/Dockerfile").read_text()
    backend = (
        "python -m pip install --no-cache-dir -r requirements/stewardship-build.txt"
    )
    editable = (
        "python -m pip install --no-cache-dir --no-deps --no-build-isolation -e ."
    )
    assert dockerfile.index(backend) < dockerfile.index(editable)


@pytest.mark.parametrize("document", ["README.md", "docs/development/stewardship.md"])
def test_checkout_instructions_match_ci_installation(document):
    """Documented pip installs use the same ordered commands as the CI baseline."""
    text = (ROOT / document).read_text()
    assert "\n".join(INSTALL_COMMANDS) in text
    assert "python -m pip install -r requirements.txt" not in text


@pytest.mark.parametrize(
    "step_name", ["Scoped line and branch coverage", "Migration drift"]
)
def test_readme_documents_ci_validation_commands(step_name):
    """Local validation includes CI's coverage gates and test-settings drift check."""
    definition = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    step = next(
        step
        for step in definition["jobs"]["validate"]["steps"]
        if step.get("name") == step_name
    )
    command = step["run"].replace(
        '"$RUNNER_TEMP/stewardship-coverage.json"',
        "/absolute/temporary/path/coverage.json",
    )
    if step.get("env"):
        command = " ".join(f"{key}={value}" for key, value in step["env"].items()) + (
            " " + command
        )
    readme = (ROOT / "README.md").read_text()
    validation = readme.split("### Local validation (matching CI)\n", 1)[1].split(
        "\n### ", 1
    )[0]
    assert command in validation
    assert "docs/development/stewardship-compose.md#validation" in validation
