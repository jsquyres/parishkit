# Stewardship development baseline

This is implementation evidence for
[ARC-01](../tasks/stewardship/architecture.md#arc-01-dependency-decisions-and-package-skeleton),
not a replacement for the [architecture specification](../specs/stewardship/architecture/spec.md).

## Supported dependency lines

The initial baseline was resolved on September 7, 2026. Python package ranges
live in `pyproject.toml`; exact transitive development/test versions live in
`requirements/stewardship.txt`. Stewardship remains an optional package extra
for users of other ParishKit tools. The repository development install includes
it so normal CI exercises the new code without provider credentials.

| Component | Selected line / initial pin | Upstream authority |
| --- | --- | --- |
| Python | 3.12 baseline; package minimum 3.12 | [Python lifecycle](https://devguide.python.org/versions/) |
| Django | 5.2 LTS / 5.2.17 | [Maintained releases](https://www.djangoproject.com/download/) |
| PostgreSQL | 18 / 18.6 | [PostgreSQL downloads](https://www.postgresql.org/download/) |
| Celery | 5.6 / 5.6.3 | [Celery changes](https://docs.celeryq.dev/en/stable/changelog.html) |
| Valkey | 9.1 / 9.1.2 | [Valkey releases](https://valkey.io/download/releases/) |
| Caddy | 2.11 / 2.11.4 | [Caddy releases](https://github.com/caddyserver/caddy/releases) |
| Gunicorn | 26 / lockfile patch | [Gunicorn releases](https://gunicorn.org/news/) |
| Psycopg | 3.3 / 3.3.5 | [Psycopg downloads](https://www.psycopg.org/download/) |
| Cryptography | 50 / 50.0.1 | [Cryptography documentation](https://cryptography.io/en/stable/) |
| PyNaCl | 1.6 / 1.6.2 | [PyNaCl changes](https://github.com/pyca/pynacl/blob/main/CHANGELOG.rst) |

The `redis` Python distribution in the lockfile is Celery's protocol client,
not a Redis server. The server choice remains Valkey. Gunicorn runs in Linux
containers; Windows host tests do not install it. Timezone data is explicitly
installed for Windows and minimal-container parity.

Browser support targets the latest two stable Chrome, Edge, Firefox, and Safari
major releases at each release candidate, including iOS Safari and Android
Chrome. ARC-08/OPS-09 record exact tested browser versions and accessibility
evidence; this scaffold does not claim browser certification.

Patch upgrades regenerate the lock and run all baseline checks. Minor/major
changes also require compatibility review of affected specifications, database
migrations, cryptographic formats, and Compose service behavior. Valkey upgrades
must pass the architecture's broker/cache/limiter/outage integration matrix.
Do not use unpinned `latest` images. OPS-01 records concrete image digests when
the container topology lands. A newer Python version needs its own full suite
before being described as a tested runtime.

Regenerate the universal dependency lock with uv 0.12.10:

```sh
uv pip compile pyproject.toml --all-extras --universal --python-version 3.12 --output-file requirements/stewardship.txt
```

Install from the checkout:

```sh
python -m pip install -r requirements.txt
```

The constraints pin dependency versions on supported platforms, not artifact
hashes or the entire build toolchain. Image/build reproducibility belongs to
OPS-01. Editable installation keeps local source changes immediately visible.

## Scaffold commands and limits

```sh
pk-stewardship --version
pk-stewardship --config scripts/pk-stewardship/example-config.yaml config-check
DJANGO_SETTINGS_MODULE=parishkit.stewardship.settings.development python -m django check
DJANGO_SETTINGS_MODULE=parishkit.stewardship.settings.development python -m django runserver 127.0.0.1:8000
python -m pytest
```

These shell environment-assignment examples are for POSIX hosts; use the same
environment variables through PowerShell or the forthcoming development Compose
configuration on Windows.

The Family and Admin routes intentionally return 503 without collecting data.
Internal liveness returns 200 without dependency access, readiness remains 503,
and metrics returns 404 until its authentication is implemented. Bind the
development server only to loopback; it is not a public deployment. Internal
route ingress isolation is delivered by ARC-03/OPS-01.

No profile uses SQLite or sends mail. Pure/HTTP tests require no database;
database tests will use PostgreSQL 18. Production settings intentionally refuse
startup until ARC-02's deployment checks are available. This refusal is not a
substitute for the remaining configuration, cryptographic, and admission work.

The eight Django app labels use the `stewardship_` prefix. Treat these labels as
stable before adding migrations. No app currently defines models or migrations.
