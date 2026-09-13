"""Deterministic, complete test partitions for isolated CI database runners."""

import hashlib
from pathlib import Path


def partition(nodeids: list[str], index: int, count: int) -> list[str]:
    """Assign every unique test once, independently of collection ordering."""
    if (
        type(index) is not int
        or type(count) is not int
        or not 1 <= index <= count <= 32
        or len(nodeids) != len(set(nodeids))
    ):
        raise ValueError("Invalid or duplicate CI test partition")
    return sorted(
        node
        for node in nodeids
        if int.from_bytes(hashlib.sha256(node.encode()).digest(), "big") % count
        == index - 1
    )


def tree_digest(root: Path) -> str:
    """Bind evidence to source, tests, dependency locks and validation settings."""
    paths = {root / "pyproject.toml", root / "coverage-stewardship.toml"}
    for directory, pattern in (
        ("src", "*.py"),
        ("src", "*.sql"),
        ("tests", "*.py"),
        ("requirements", "*.txt"),
        (".github/workflows", "*.yml"),
    ):
        paths.update((root / directory).rglob(pattern))
    paths.update(root.glob("requirements*.txt"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file():
            raise ValueError("CI evidence requires real repository inputs")
        name = path.relative_to(root).as_posix().encode()
        body = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big") + name)
        digest.update(len(body).to_bytes(8, "big") + body)
    return digest.hexdigest()
