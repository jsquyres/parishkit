# parishkit-print-member

Look up ParishSoft family and member records.

This wrapper delegates to the installed `parishkit-print-member` command. The
implementation is added in the print-member migration phase.

Current skeleton status: only `--version` is expected to succeed until this
command is implemented.

## Planned Usage

```sh
parishkit-print-member --config example-config.yaml --member-duid 12345
```

Use runtime credential paths in local config. Do not store API keys in this
directory.
