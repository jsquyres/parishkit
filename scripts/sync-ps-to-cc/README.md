# parishkit-sync-ps-to-cc

Synchronize ParishSoft contacts to Constant Contact lists.

This wrapper delegates to the installed `parishkit-sync-ps-to-cc` command. The
implementation is added in the sync-ps-to-cc migration phase.

Current skeleton status: only `--version` is expected to succeed until this
command is implemented.

## Planned Usage

```sh
parishkit-sync-ps-to-cc --config example-config.yaml --dry-run
```

Keep ParishSoft, Constant Contact, and email credentials outside git.
