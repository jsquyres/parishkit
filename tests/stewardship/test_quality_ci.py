"""Isolated CI partitions must account for every test and combine real coverage."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from coverage import Coverage

from parishkit.stewardship import quality_ci as ci
from parishkit.stewardship.quality_sharding import partition, tree_digest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("count", [1, 2, 8, 32])
def test_complete_disjoint_stable_partition(count):
    """Every newly collected test is assigned exactly once, without a file list."""
    nodes = [f"tests/stewardship/database/test_a.py::test_{n}" for n in range(1000)]
    groups = [partition(nodes, index, count) for index in range(1, count + 1)]
    assert sorted(node for group in groups for node in group) == sorted(nodes)
    assert groups == [partition(nodes[::-1], i, count) for i in range(1, count + 1)]


@pytest.mark.parametrize("index,count", [(0, 8), (9, 8), (1, 0), (1, 33), (True, 8)])
def test_invalid_partition(index, count):
    """Invalid bounds never silently select a successful empty shard."""
    with pytest.raises(ValueError):
        partition([], index, count)


def test_duplicate_collection_rejected():
    """Duplicate IDs are not silently deduplicated."""
    with pytest.raises(ValueError):
        partition(["same", "same"], 1, 2)


@pytest.fixture
def repository(tmp_path):
    """Build two branch-bearing source files and the actual coverage manifest."""
    root = tmp_path / "checkout"
    package = root / "src/parishkit/stewardship"
    package.mkdir(parents=True)
    code = "if value:\n    answer = 1\nelse:\n    answer = 2\n"
    (package / "__init__.py").write_text(code)
    (root / "src/parishkit/shared.py").write_text(code)
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (root / "coverage-stewardship.toml").write_text(
        'schema_version = 1\nshared_modules = ["src/parishkit/shared.py"]\n'
    )
    return root


def artifacts(root, tmp_path, monkeypatch):
    """Produce genuine raw coverage for opposite branches in two separate jobs."""
    directory = tmp_path / "artifacts"
    nodes = [f"tests/stewardship/database/test_a.py::test_{n}" for n in range(20)]
    monkeypatch.setattr(ci, "database_collection", lambda root: sorted(nodes))
    for index in (1, 2):
        output = directory / str(index)
        output.mkdir(parents=True)
        data = output / "coverage.data"
        cov = Coverage(data_file=str(data), branch=True, config_file=False)
        cov.start()
        for path in sorted((root / "src").rglob("*.py")):
            exec(compile(path.read_text(), str(path), "exec"), {"value": index == 1})
        cov.stop()
        cov.save()
        selected = partition(nodes, index, 2)
        tests = output / "tests.json"
        tests.write_text(
            json.dumps(
                {
                    "universe": sorted(nodes),
                    "selected": selected,
                    "completed": selected,
                }
            )
        )
        (output / "receipt.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "index": index,
                    "count": 2,
                    "root": str(root),
                    "tree": tree_digest(root),
                    "data_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
                    "tests_sha256": hashlib.sha256(tests.read_bytes()).hexdigest(),
                }
            )
        )
    return directory


def test_real_coverage_union(repository, tmp_path, monkeypatch, capsys):
    """Opposite partial branches combine to 100%, rather than being averaged."""
    directory = artifacts(repository, tmp_path, monkeypatch)
    assert ci.combine(repository, directory, tmp_path / "combined.json", 2) == 0
    assert "lines 100.00%; branches 100.00%" in capsys.readouterr().out
    assert (directory / "1/coverage.data").is_file()


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "duplicate",
        "stale",
        "data",
        "tests",
        "selection",
        "universe",
        "count",
        "schema",
        "outside",
        "report_exists",
    ],
)
def test_incomplete_evidence_fails(repository, tmp_path, monkeypatch, problem):
    """Reject incomplete/mismatched execution, source or raw coverage artifacts."""
    directory = artifacts(repository, tmp_path, monkeypatch)
    path = directory / "2/receipt.json"
    receipt = json.loads(path.read_text())
    report = tmp_path / "combined.json"
    if problem == "missing":
        path.unlink()
    elif problem == "duplicate":
        receipt["index"] = 1
    elif problem == "stale":
        (repository / "src/parishkit/shared.py").write_text("answer = 3\n")
    elif problem == "data":
        (directory / "2/coverage.data").write_bytes(b"invalid")
    elif problem == "tests":
        (directory / "2/tests.json").write_text("{}")
    elif problem in {"selection", "universe"}:
        tests = directory / "2/tests.json"
        evidence = json.loads(tests.read_text())
        evidence["selected" if problem == "selection" else "universe"].pop()
        tests.write_text(json.dumps(evidence))
        receipt["tests_sha256"] = hashlib.sha256(tests.read_bytes()).hexdigest()
    elif problem in {"count", "schema"}:
        receipt[problem] = 99
    elif problem == "outside":
        receipt["root"] = str(repository / "wrong")
    elif problem == "report_exists":
        report.write_text("old report")
    if problem != "missing":
        path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        ci.combine(repository, directory, report, 2)


@pytest.mark.parametrize("baseline,database", [(1, 0), (0, 1), (0, 5)])
def test_failed_shard_never_publishes_receipt(
    repository, tmp_path, monkeypatch, baseline, database
):
    """A passing baseline cannot mask failed or empty database execution."""
    run = Mock(
        side_effect=[
            subprocess.CompletedProcess([], baseline),
            subprocess.CompletedProcess([], database),
        ]
    )
    monkeypatch.setattr(ci.subprocess, "run", run)
    output = tmp_path / "shard"
    assert ci.run_shard(repository, output, 1, 8) == (baseline or database)
    assert not (output / "receipt.json").exists()
    assert run.call_count == (1 if baseline else 2)
    if not baseline:
        command = run.call_args.args[0]
        assert "--require-postgresql-tests" in command
        assert "--ci-shard=1/8" in command
        assert "--cov-append" in command
        assert "faulthandler_timeout=120" in command
        assert run.call_args.kwargs["timeout"] == ci.SHARD_TIMEOUT


def test_hung_child_fails_without_receipt(repository, tmp_path, monkeypatch):
    """The finite subprocess deadline cannot create passing coverage evidence."""
    monkeypatch.setattr(
        ci.subprocess,
        "run",
        Mock(
            side_effect=subprocess.TimeoutExpired([], 1),
        ),
    )
    output = tmp_path / "shard"
    assert (
        ci.main(
            [
                "shard",
                "--root",
                str(repository),
                "--index",
                "1",
                "--count",
                "8",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not (output / "receipt.json").exists()


def test_digest_tracks_schema_sql_too(repository):
    """Identical Python with changed SQL cannot reuse old passing artifacts."""
    first = tree_digest(repository)
    (repository / "src/parishkit/initial.sql").write_text("SELECT 1;")
    assert first != tree_digest(repository)


@pytest.mark.parametrize(
    "body,code",
    [
        ("pass", 0),
        ("assert False", 1),
        ('pytest.skip("synthetic")', 1),
    ],
)
def test_actual_plugin_execution_receipt(tmp_path, body, code):
    """Run real pytest hooks without needing database fixtures or credentials."""
    root = tmp_path / "probe"
    directory = root / "tests/stewardship/database"
    directory.mkdir(parents=True)
    shutil.copyfile(ROOT / "tests/conftest.py", root / "tests/conftest.py")
    (root / "pytest.ini").write_text("[pytest]\n")
    (directory / "test_probe.py").write_text(
        "import pytest\n@pytest.mark.parametrize('n', range(20))\n"
        f"def test_probe(n):\n    {body}\n"
    )
    evidence = tmp_path / "tests.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/stewardship/database",
            "-q",
            "--ds=parishkit.stewardship.settings.database_test",
            "--require-postgresql-tests",
            "--ci-shard=1/2",
            f"--ci-evidence={evidence}",
        ],
        cwd=root,
        env=ci.environment(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == code, result.stdout + result.stderr
    assert "CI_PROGRESS" in result.stdout and "START" in result.stdout
    assert "END" in result.stdout and "elapsed=" in result.stdout
    assert evidence.exists() is (code == 0)
    if code == 0:
        data = json.loads(evidence.read_text())
        assert len(data["universe"]) == 20
        assert (
            data["completed"] == data["selected"] == partition(data["universe"], 1, 2)
        )
