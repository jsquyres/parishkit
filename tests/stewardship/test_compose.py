"""Credential-free Compose contracts; daemon-dependent checks are opt-in."""

import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener
from uuid import uuid4

import pytest
import yaml

from parishkit.stewardship.deployment import SECRET_NAMES
from parishkit.stewardship.services import prepare_development

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy/stewardship"


def collection_manifest(output):
    """Require one nonempty, typed manifest rather than scraping pytest prose."""
    prefix = "PARISHKIT_TEST_NODEIDS="
    manifests = [
        line[len(prefix) :] for line in output.splitlines() if line.startswith(prefix)
    ]
    assert len(manifests) == 1, "Expected exactly one test collection manifest"
    nodes = json.loads(manifests[0])
    assert isinstance(nodes, list) and nodes, "Expected a nonempty node-ID list"
    assert all(isinstance(node, str) and node for node in nodes), "Invalid test node ID"
    return Counter(nodes)


def assert_collection_parity(host_output, image_output):
    """Compare exact IDs and multiplicity, ignoring only collection order."""
    host = collection_manifest(host_output)
    image = collection_manifest(image_output)
    missing = sorted((host - image).elements())
    unexpected = sorted((image - host).elements())
    assert not missing and not unexpected, (
        f"Host/container collection differs. Missing in image: {missing}; "
        f"unexpected in image: {unexpected}"
    )


@pytest.mark.parametrize(
    "output",
    [
        "10 tests collected",
        "PARISHKIT_TEST_NODEIDS=[]",
        'PARISHKIT_TEST_NODEIDS={"test": 1}',
        "PARISHKIT_TEST_NODEIDS=[1]",
        'PARISHKIT_TEST_NODEIDS=[""]',
        "PARISHKIT_TEST_NODEIDS=not-json",
        'PARISHKIT_TEST_NODEIDS=["a"]\nPARISHKIT_TEST_NODEIDS=["a"]',
    ],
)
def test_collection_manifest_rejects_missing_or_invalid_evidence(output):
    """Empty, malformed, or ambiguous evidence must never look like parity."""
    with pytest.raises((AssertionError, ValueError)):
        collection_manifest(output)


def test_collection_parity_ignores_order_and_unrelated_output():
    """Terminal headings and order are irrelevant; parameterized IDs stay exact."""
    assert_collection_parity(
        'header\nPARISHKIT_TEST_NODEIDS=["test[a]", "test[b]"]\n2 tests collected',
        'PARISHKIT_TEST_NODEIDS=["test[b]", "test[a]"]\n2 passed',
    )


@pytest.mark.parametrize("image", [["a"], ["a", "c"], ["a", "b", "b"]])
def test_collection_parity_detects_missing_replaced_and_duplicate_tests(image):
    """Equal counts cannot hide a replacement, and duplicates remain visible."""
    with pytest.raises(AssertionError, match="Host/container collection differs"):
        assert_collection_parity(
            'PARISHKIT_TEST_NODEIDS=["a", "b"]',
            "PARISHKIT_TEST_NODEIDS=" + json.dumps(image),
        )


def test_collection_manifest_hook_reports_parameterized_and_skipped_tests(tmp_path):
    """Real collection emits portable node IDs without executing test bodies."""
    shutil.copyfile(ROOT / "tests/conftest.py", tmp_path / "conftest.py")
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_sample.py").write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('value', ['alpha', 'beta'])\n"
        "def test_case(value):\n"
        "    raise AssertionError('collection must not execute tests')\n"
        "@pytest.mark.skip(reason='synthetic skip')\n"
        "def test_skipped():\n"
        "    pass\n"
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PYTEST_") and key != "DJANGO_SETTINGS_MODULE"
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "--collection-manifest",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert collection_manifest(result.stdout) == Counter(
        [
            "test_sample.py::test_case[alpha]",
            "test_sample.py::test_case[beta]",
            "test_sample.py::test_skipped",
        ]
    )


def definition(name):
    """Read a committed Compose input without needing a Docker installation."""
    return yaml.safe_load((DEPLOY / name).read_text())


def test_scaffold_roles_have_no_accidental_authority():
    """Pending identities are distinct, unprivileged, and hold no live secrets."""
    base = definition("compose.yaml")
    app_services = {
        name: service
        for name, service in base["services"].items()
        if name not in {"postgres", "valkey"}
    }
    targets = SECRET_NAMES - {"handoff_private"}
    expected = {
        "credential-installer-" + target.replace("_", "-") for target in targets
    }
    assert expected <= app_services.keys()
    installers = [app_services[name] for name in sorted(expected)]
    assert len({service["user"] for service in installers}) == len(targets)
    for name, service in app_services.items():
        assert service["user"].split(":")[0] != "0"
        assert service["read_only"] and service["init"]
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert not service.get("volumes") and not service.get("ports")
        if name != "web":
            assert service["profiles"]
            assert service["healthcheck"]["disable"]
    assert base["services"]["bootstrap"]["profiles"] == ["bootstrap"]
    assert base["networks"]["backend"]["internal"]
    for name in ("postgres", "valkey"):
        service = base["services"][name]
        assert "@sha256:" in service["image"]
        assert not service.get("ports")
        for mount in service["volumes"]:
            assert not mount["bind"]["create_host_path"]
            assert "PARISHKIT_ROOT:-/opt/parishkit" in mount["source"]


def test_development_and_production_overlays():
    """Live code is read-only in development and absent from production inputs."""
    development = definition("compose.development.yaml")
    web = development["services"]["web"]
    assert web["ports"] == ["127.0.0.1:${STEWARDSHIP_HTTP_PORT:-8000}:8000"]
    assert web["volumes"][0]["target"] == "/app/src"
    assert web["volumes"][0]["read_only"]
    production = definition("compose.production.yaml")
    for name, service in production["services"].items():
        assert "build" not in service
        if name not in {"caddy", "postgres"}:
            assert service["image"].startswith("ghcr.io/")
            assert "@sha256:${STEWARDSHIP_IMAGE_SHA256:?" in service["image"]
            assert not service.get("ports") and not service.get("volumes")
    assert production["services"]["caddy"]["ports"] == ["80:80", "443:443"]
    assert production["services"]["caddy"]["profiles"] == ["pending-ingress"]


def test_test_fixture_mounts_require_existing_read_only_sources():
    """A missing checkout fixture must fail mounting, never create a directory."""
    mounts = definition("compose.development.yaml")["services"]["tests"]["volumes"]
    targets = set()
    for mount in mounts:
        assert isinstance(mount, dict), "Test mounts must use explicit long syntax"
        assert mount["type"] == "bind" and mount["read_only"] is True
        assert mount["bind"]["create_host_path"] is False
        source = (DEPLOY / mount["source"]).resolve()
        assert source.exists()
        assert mount["target"] == "/app/" + source.relative_to(ROOT).as_posix()
        assert mount["target"] not in targets
        targets.add(mount["target"])


def compose_environment(root):
    """Isolate tests from local operator Compose/deployment configuration."""
    return {
        **{
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("STEWARDSHIP_", "COMPOSE_", "PARISHKIT_"))
        },
        "PARISHKIT_ROOT": str(root),
        "STEWARDSHIP_GHCR_REPOSITORY": "example/parishkit",
        "STEWARDSHIP_IMAGE_SHA256": "0" * 64,
        "STEWARDSHIP_HOSTNAME": "stewardship.example.invalid",
        "STEWARDSHIP_PRODUCTION_POSTGRES_PASSWORD_FILE": str(root / "prod-db-password"),
        "STEWARDSHIP_CADDY_CONFIG_FILE": str(root / "Caddyfile"),
    }


@pytest.mark.skipif(
    os.environ.get("PARISHKIT_RUN_COMPOSE_TESTS") != "1",
    reason="explicit opt-in required for pinned Caddy validation",
)
def test_caddy_template_denies_internal_paths_before_proxy():
    """Validate the real template without serving traffic or requesting TLS.

    Pass only committed template text and a synthetic hostname to the pinned
    image. No host configuration, credentials, ports, or networks are attached.
    Exact route assertions intentionally require review of matcher/order changes.
    """
    hostname = "stewardship.example.invalid"
    image = definition("compose.production.yaml")["services"]["caddy"]["image"]
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/config",
            "--tmpfs",
            "/data",
            "--env",
            f"STEWARDSHIP_HOSTNAME={hostname}",
            image,
            "caddy",
            "adapt",
            "--config",
            "-",
            "--adapter",
            "caddyfile",
            "--validate",
        ],
        input=(DEPLOY / "Caddyfile").read_text(),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    config = json.loads(result.stdout)
    (server,) = config["apps"]["http"]["servers"].values()
    # Guard every enclosing route too: a correct denial hidden behind another
    # matcher or a preceding catch-all would not protect the internal endpoints.
    internal = {
        "match": [{"path": ["/health/live", "/health/ready", "/metrics"]}],
        "handle": [{"handler": "static_response", "status_code": 404}],
    }
    proxy = {
        "handle": [{"handler": "reverse_proxy", "upstreams": [{"dial": "web:8000"}]}]
    }
    ordered = {"handler": "subroute", "routes": [internal, proxy]}
    site = {"handler": "subroute", "routes": [{"handle": [ordered]}]}
    assert server["routes"] == [
        {"match": [{"host": [hostname]}], "handle": [site], "terminal": True}
    ]


@pytest.mark.skipif(
    os.environ.get("PARISHKIT_RUN_COMPOSE_TESTS") != "1",
    reason="explicit opt-in required for Docker build-context checks",
)
@pytest.mark.parametrize("ignore_kind", ["root", "dockerfile"])
def test_build_context_excludes_synthetic_private_files(tmp_path, ignore_kind):
    """Exercise each ignore file alone using only a synthetic scratch context.

    COPY of the entire filtered context makes missed exclusions observable.
    Export locally without publishing or loading an image, pulling a base, or
    submitting any real checkout configuration/credentials to the builder.
    """
    context = tmp_path / "context"
    dockerfile = context / "deploy/stewardship/Dockerfile"
    dockerfile.parent.mkdir(parents=True)
    dockerfile.write_text("FROM scratch\nCOPY . /\n")
    if ignore_kind == "root":
        shutil.copyfile(ROOT / ".dockerignore", context / ".dockerignore")
    else:
        shutil.copyfile(
            DEPLOY / "Dockerfile.dockerignore",
            dockerfile.with_name("Dockerfile.dockerignore"),
        )
    allowed = {
        "README.md",
        "pyproject.toml",
        "requirements/stewardship.txt",
        "requirements/stewardship-build.txt",
        "src/parishkit/app.py",
        "src/parishkit/static/logo.svg",
        "src/parishkit/templates/page.html",
    }
    denied = {
        ".git/config",
        ".venv/credentials",
        ".coverage",
        ".env",
        "config/parish.yaml",
        "credentials/token",
        "opt/parishkit/credentials/key",
        "src/parishkit/private.yaml",
        "src/parishkit/__pycache__/app.pyc",
        "requirements/local.txt",
        "new-unlisted-directory/private.py",
    }
    for relative in allowed | denied:
        path = context / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic fixture\n")
    output = tmp_path / "export"
    subprocess.run(
        [
            "docker",
            "buildx",
            "build",
            "--file",
            str(dockerfile),
            "--output",
            f"type=local,dest={output}",
            str(context),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    exported = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert exported == allowed


@pytest.mark.skipif(
    os.environ.get("PARISHKIT_RUN_COMPOSE_TESTS") != "1",
    reason="explicit opt-in required for Docker Compose checks",
)
@pytest.mark.parametrize("profile", ["development", "production"])
def test_rendered_compose_contract(profile, tmp_path):
    """Check actual Compose merges without starting or deploying production."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--profile",
            "*",
            "--env-file",
            os.devnull,
            "-f",
            str(DEPLOY / "compose.yaml"),
            "-f",
            str(DEPLOY / f"compose.{profile}.yaml"),
            "config",
            "--format",
            "json",
        ],
        env=compose_environment(tmp_path),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    config = json.loads(result.stdout)
    expected_services = set(definition("compose.yaml")["services"]) | set(
        definition(f"compose.{profile}.yaml")["services"]
    )
    assert set(config["services"]) == expected_services
    if profile == "development":
        fixtures = definition("compose.development.yaml")["services"]["tests"][
            "volumes"
        ]
        expected_mounts = {
            mount["target"]: str((DEPLOY / mount["source"]).resolve())
            for mount in fixtures
        }
        mounts = config["services"]["tests"]["volumes"]
        assert {mount["target"]: mount["source"] for mount in mounts} == expected_mounts
        for mount in mounts:
            assert mount["type"] == "bind" and mount["read_only"] is True
            # Compose may omit a false boolean when serializing normalized JSON.
            assert mount.get("bind", {}).get("create_host_path", False) is False
    for name, service in config["services"].items():
        if name not in {"web", "caddy"}:
            assert not service.get("ports")
        if profile == "production":
            assert not service.get("build")
            if name != "caddy":
                assert not service.get("ports")
            for mount in service.get("volumes", []):
                assert not mount["source"].startswith(str(ROOT))
    for service, target in [("postgres", "/var/lib/postgresql"), ("valkey", "/data")]:
        mounts = config["services"][service]["volumes"]
        mount = next(item for item in mounts if item["target"] == target)
        directory = "postgresql" if service == "postgres" else service
        assert mount["source"] == str(tmp_path / "run/persistent" / directory)
    if profile == "production":
        mounts = config["services"]["postgres"]["volumes"]
        password = next(
            item for item in mounts if item["target"].startswith("/run/secrets")
        )
        assert password["source"] == str(tmp_path / "prod-db-password")


def wait_http(origin, path, status, body=None):
    """Boundedly poll an isolated container, including expected error responses."""
    deadline = time.monotonic() + 30
    opener = build_opener(ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            try:
                response = opener.open(origin + path, timeout=2)
            except HTTPError as error:
                response = error
            with response:
                if response.status == status and (
                    body is None or response.read() == body
                ):
                    return
        except (URLError, OSError):
            pass
        time.sleep(0.2)
    pytest.fail(f"Scaffold endpoint did not reach expected status {status}")


@pytest.mark.skipif(
    os.environ.get("PARISHKIT_RUN_COMPOSE_SMOKE") != "1",
    reason="explicit opt-in required for disposable local Docker services",
)
def test_development_container_lifecycle(tmp_path):
    """Start isolated services; verify reload, private ports, and replacement.

    Use a copied source tree so no test mutates the developer's live checkout.
    Cleanup removes only this UUID-named project's containers/networks, never
    volumes or host data. Synthetic durable files remain under pytest's temp
    directory for inspection. No production Compose or provider is invoked.
    """
    runtime = tmp_path / "runtime"
    prepare_development(runtime)
    source = tmp_path / "source"
    shutil.copytree(ROOT / "src", source, ignore=shutil.ignore_patterns("__pycache__"))
    override = tmp_path / "source.yaml"
    override.write_text(
        yaml.safe_dump(
            {
                "services": {
                    "web": {
                        "volumes": [
                            {
                                "type": "bind",
                                "source": str(source),
                                "target": "/app/src",
                                "read_only": True,
                            }
                        ]
                    }
                }
            }
        )
    )
    environment = compose_environment(runtime)
    environment["STEWARDSHIP_HTTP_PORT"] = "0"
    project = "pk-stewardship-smoke-" + uuid4().hex[:12]
    prefix = [
        "docker",
        "compose",
        "--env-file",
        os.devnull,
        "-p",
        project,
        "-f",
        str(DEPLOY / "compose.yaml"),
        "-f",
        str(DEPLOY / "compose.development.yaml"),
        "-f",
        str(override),
    ]

    def compose(*arguments, check=True, timeout=120):
        """Run only against the fresh disposable project, preserving error output."""
        result = subprocess.run(
            [*prefix, *arguments],
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode:
            pytest.fail(result.stdout + result.stderr)
        return result

    try:
        # Collect independently on the host; never use the outer invocation's
        # selection (-k, a single test file, etc.) as the complete baseline.
        host_environment = {
            key: value
            for key, value in environment.items()
            if not key.startswith("PYTEST_")
        }
        host_environment["DJANGO_SETTINGS_MODULE"] = (
            "parishkit.stewardship.settings.test"
        )
        host_collection = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests",
                "--collect-only",
                "--collection-manifest",
                "-q",
                "-o",
                "addopts=",
                "-p",
                "no:cacheprovider",
            ],
            cwd=ROOT,
            env=host_environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        baseline = compose(
            "run",
            "--rm",
            "--no-deps",
            "tests",
            "tests",
            "--collection-manifest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
        )
        assert_collection_parity(host_collection.stdout, baseline.stdout)
        # Keep human-readable test evidence without repeating hundreds of IDs.
        print(
            "\n".join(
                line
                for line in baseline.stdout.splitlines()
                if not line.startswith("PARISHKIT_TEST_NODEIDS=")
            )
        )
        compose("up", "--wait", "--wait-timeout", "90", "web", "postgres", "valkey")
        assert compose("exec", "-T", "web", "id", "-u").stdout.strip() == "10001"
        origin = "http://" + compose("port", "web", "8000").stdout.strip()
        wait_http(origin, "/health/live", 200, b"ok\n")
        for path in ("/", "/admin/", "/family/", "/health/ready"):
            wait_http(origin, path, 503)
        wait_http(origin, "/metrics", 404)
        sentinel = "synthetic-private-access-sentinel"
        wait_http(origin, "/access/" + sentinel + "?code=synthetic-private-query", 503)
        logs = compose("logs", "--no-color", "web").stdout
        assert sentinel not in logs and "synthetic-private-query" not in logs

        # A Python-only source change must be visible without image rebuild or
        # container replacement. Updating fixture mtime avoids one-second races.
        views = source / "parishkit/stewardship/views.py"
        original = views.read_text()
        assert '"ok\\n"' in original
        views.write_text(original.replace('"ok\\n"', '"reloaded\\n"'))
        os.utime(views, (time.time() + 2, time.time() + 2))
        wait_http(origin, "/health/live", 200, b"reloaded\n")
        views.write_text(original)
        os.utime(views, (time.time() + 4, time.time() + 4))
        wait_http(origin, "/health/live", 200, b"ok\n")

        config = json.loads(compose("config", "--format", "json").stdout)
        for name in ("postgres", "valkey"):
            assert not config["services"][name].get("ports")
        compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "stewardship",
            "-c",
            "CREATE TABLE scaffold_probe (value text); "
            "INSERT INTO scaffold_probe VALUES ('synthetic-persistent-value');",
        )
        compose(
            "exec", "-T", "valkey", "valkey-cli", "SET", "scaffold-probe", "durable"
        )
        compose(
            "up",
            "--force-recreate",
            "--wait",
            "--wait-timeout",
            "90",
            "postgres",
            "valkey",
        )
        result = compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "stewardship",
            "-Atc",
            "SELECT value FROM scaffold_probe",
        )
        assert result.stdout.strip() == "synthetic-persistent-value"
        assert (
            compose(
                "exec", "-T", "valkey", "valkey-cli", "GET", "scaffold-probe"
            ).stdout.strip()
            == "durable"
        )

        refusal = compose(
            "run",
            "--rm",
            "--no-deps",
            "web",
            "service",
            "--profile",
            "production",
            "--service-role",
            "web",
            check=False,
        )
        assert refusal.returncode == 2 and "startup refused" in refusal.stderr
        compose("stop", "--timeout", "10", "web")
        stopped = json.loads(compose("ps", "--all", "--format", "json", "web").stdout)
        assert stopped["State"] == "exited" and stopped["ExitCode"] != 137
        compose("up", "--wait", "--wait-timeout", "30", "web")
        origin = "http://" + compose("port", "web", "8000").stdout.strip()
        wait_http(origin, "/health/live", 200, b"ok\n")
    finally:
        compose("down", "--timeout", "10", timeout=60)
