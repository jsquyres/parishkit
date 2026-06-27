# parishkit-sync-google-group

Synchronize Google Group membership from configured ParishSoft sources.

This wrapper delegates to the installed `parishkit-sync-google-group` command.
The implementation is added in the sync-google-group migration phase.

Current skeleton status: only `--version` is expected to succeed until this
command is implemented.

## Planned Usage

```sh
parishkit-sync-google-group --config example-config.yaml --dry-run
```

Keep ParishSoft, Google, and email credentials outside git.
