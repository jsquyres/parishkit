# Stewardship command

Install with `python -m pip install -r requirements.txt` from the checkout.
Run `pk-stewardship --version` or
`pk-stewardship --config scripts/pk-stewardship/example-config.yaml config-check`.
The wrapper in this directory delegates to the same package entry point.

`config-check` currently checks YAML readability/mapping syntax only. It prints
no keys, values, or secret paths and explicitly reports that deployment has
not been validated. It does not initialize Django or contact a provider.
No bootstrap, publish, purge, or other mutating command is available yet.

`validate-deployment` checks the typed deployment metadata, including profile,
origin, proxy hops, service role, paths, and connection settings. It prints only
success flags, explicitly distinguishing metadata validation from startup
readiness. `--profile`, `--service-role`, `--public-origin`, and `--runtime-root`
override the corresponding environment/YAML settings. See the
[deployment schema](../../docs/development/stewardship-deployment.md).

For the current implementation scope, see the
[architecture tasks](../../docs/tasks/stewardship/architecture.md) and
[dependency and development notes](../../docs/development/stewardship.md).
