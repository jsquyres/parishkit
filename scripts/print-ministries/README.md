# parishkit-print-ministries

Print ParishSoft ministry names in sorted order.

This wrapper delegates to the installed `parishkit-print-ministries` command.
The implementation is added in the print-ministries migration phase.

Current skeleton status: only `--version` is expected to succeed until this
command is implemented.

## Planned Usage

```sh
parishkit-print-ministries --config example-config.yaml
```

Use runtime credential paths in local config. Do not store API keys in this
directory.
