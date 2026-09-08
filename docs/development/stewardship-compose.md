# Stewardship Compose scaffold

[Developer overview](stewardship.md) ·
[Operations tasks](../tasks/stewardship/operations.md#ops-01-development-and-production-compose-topology)

This is the Phase 0 scaffold, not a usable campaign system or an approved
production deployment. HTTP serves intentional unavailable pages and liveness.
Readiness remains `503`. PostgreSQL and Valkey run independently; application
database/broker integration follows in Phase 1.

## Local development

Install Docker Engine/Desktop with Compose v2+, Python 3.12+, and the
[development environment](stewardship.md). Run from the repository root. The same
Linux image runs on Linux hosts and Docker Desktop for macOS/Windows. Docker
must be allowed to share the checkout and runtime directory.

Choose a new runtime directory outside the checkout whose parent already exists.
On Linux/macOS:

```sh
export PARISHKIT_ROOT=/absolute/path/to/new-stewardship-runtime
pk-stewardship prepare-development --runtime-root "$PARISHKIT_ROOT"
docker compose -f deploy/stewardship/compose.yaml -f deploy/stewardship/compose.development.yaml build web
docker compose -f deploy/stewardship/compose.yaml -f deploy/stewardship/compose.development.yaml up --wait web postgres valkey
```

In PowerShell, substitute these first two commands, followed by the same Compose
commands:

```powershell
$env:PARISHKIT_ROOT = 'C:/absolute/path/to/new-stewardship-runtime'
pk-stewardship prepare-development --runtime-root $env:PARISHKIT_ROOT
```

Provisioning refuses an existing target, creates owner-only directories where
POSIX modes are supported, and generates a synthetic PostgreSQL password file.
It creates no parish configuration, application keys, or provider credentials.
Protect the runtime directory with equivalent Windows ACLs. After partial
failure, inspect the newly created tree and choose another new target; the
command never deletes or replaces files.

Open `http://localhost:8000/`. `/admin/` and `/family/` return `503` until their
workflows exist. `/health/live` returns `200`; `/health/ready` returns `503`;
`/metrics` returns `404`. No login, provider calls, or application database writes
occur. Production ingress will deny these internal health/metrics URLs.

Web mounts only `src/` read-only at `/app/src`. Python changes trigger Django's
development reload; packaged template/static changes are visible to subsequent
reads. There is no whole-checkout mount. Dependencies/image instructions require
a rebuild. Never place credentials in package source files.

Set `STEWARDSHIP_HTTP_PORT` to change the localhost port (default `8000`). No
database or broker port is published. Application containers use non-root
numeric identities, an init process for signals, a read-only filesystem,
temporary `/tmp`, dropped capabilities, and no-new-privileges.

Stop without deleting durable data:

```sh
docker compose -f deploy/stewardship/compose.yaml -f deploy/stewardship/compose.development.yaml down
```

Restart with the same `PARISHKIT_ROOT`. Database/broker state survives container
replacement. Never use `run/persistent` for generic cleanup.

## Configuration and unfinished boundaries

All base stores default under `PARISHKIT_ROOT`, falling back to `/opt/parishkit`.
Paths must exist; Compose does not silently create missing bind-mount targets.
The scaffold offers explicit Compose inputs:

| Variable | Meaning |
| --- | --- |
| `STEWARDSHIP_POSTGRES_PATH` | PostgreSQL durable directory |
| `STEWARDSHIP_VALKEY_PATH` | Valkey durable directory |
| `STEWARDSHIP_CADDY_PATH` | Parent of Caddy `data/` and `config/` |
| `STEWARDSHIP_POSTGRES_PASSWORD_FILE` | Local PostgreSQL password file |
| `STEWARDSHIP_HTTP_PORT` | Localhost HTTP port |

These inputs are not a second parish configuration authority. OPS-02 will
connect the [typed CLI/YAML path model](stewardship-deployment.md) to Compose
rendering/provisioning, including media/config/export overrides, optional named
volumes, and service ownership validation. The development helper currently
provisions only the standard layout.

The topology reserves general worker, scheduler, configuration installer, one
credential-installer identity per secret target, isolated mail/backup workers,
token rotation, bootstrap, and migration. Only development web is implemented.
Pending identities have no data, authority, or secret mounts and exit `2` even
when explicitly invoked; they never claim jobs or report healthy. Ordinary
startup excludes `pending`, `bootstrap`, `migration`, and `token-key-rotation`
profiles. Valkey keeps protected mode enabled, with no application clients
until authenticated role-specific queue access exists.

ARC-06/OPS-02 will attach narrow mounts and queues alongside their enforcement.
OPS-04 owns bootstrap/online exclusion, migrations, and production validation.
Do not enable these profiles to bypass unfinished prerequisites.

## Production structure, not deployment instructions

The production overlay has no build context or checkout mount. Every app role
uses one required GHCR digest, assembled from `STEWARDSHIP_GHCR_REPOSITORY`
(`owner/repository`) and `STEWARDSHIP_IMAGE_SHA256` (64 hexadecimal characters).
Docker rejects malformed digests. The overlay also requires
`STEWARDSHIP_HOSTNAME`, an operator-installed `STEWARDSHIP_CADDY_CONFIG_FILE`, and
`STEWARDSHIP_PRODUCTION_POSTGRES_PASSWORD_FILE`. Production cannot fall back to
the generated development password. Combine only one overlay with the base;
never combine development and production overlays.

Only Caddy publishes production ports (`80`/`443`). It is disabled behind the
`pending-ingress` profile until ingress/startup validation lands. The checked-in
[Caddyfile](../../deploy/stewardship/Caddyfile) is a reference template, not an
automatically installed configuration. It denies internal paths before proxying,
with access logging off pending tested redaction. Operators must copy that
template to their managed configuration location and set
`STEWARDSHIP_CADDY_CONFIG_FILE` to that file; Compose mounts only the supplied
file and does not enforce the template's contents. Installation and ingress
validation remain pending work, not a reason to enable this profile now.
Production services still refuse startup. TLS, static serving, and release
artifacts are not yet operational or approved.

Python, PostgreSQL, Valkey, and Caddy use multi-architecture image digests.
PostgreSQL 18 persists at `/var/lib/postgresql`, following its
[version-specific volume layout](https://hub.docker.com/_/postgres).
Build tools are pinned in `requirements/stewardship-build.txt`; app and test
dependencies use `requirements/stewardship.txt`. Phase 0 includes test tools
in the one image for parity. OPS-09 owns release scanning, provenance, SBOM,
and publication; no image has been published.

## Validation

Normal `python -m pytest` tests topology contracts without Docker or providers.
Run the same baseline in the built image:

```sh
docker compose -f deploy/stewardship/compose.yaml -f deploy/stewardship/compose.development.yaml run --rm --no-deps tests
```

The test-only profile mounts test/wrapper/tool fixtures read-only, not credentials
or the Docker socket. It does not inherit host Compose-smoke flags, preventing
recursive orchestration.

Opt-in host checks render both overlays and exercise a disposable development
project (build the image first):

```sh
PARISHKIT_RUN_COMPOSE_TESTS=1 PARISHKIT_RUN_COMPOSE_SMOKE=1 python -m pytest tests/stewardship/test_compose.py -q -s
```

In PowerShell, set both variables through `$env:` before invoking pytest.
The test uses a new UUID-named project and copied source tree, runs the in-image
baseline, checks routes/log suppression, verifies reload without rebuilding,
recreates PostgreSQL/Valkey with synthetic records, verifies persistence,
rejects production web startup, and restarts web. It tears down only its own
containers/networks; synthetic host data remains under pytest's temporary
directory. It never prunes volumes, deletes host data, starts production Caddy,
requests a certificate, or contacts a provider.
