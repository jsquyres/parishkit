# parishkit-create-ministry-rosters

Create ministry rosters from ParishSoft data and write them to Google Sheets.

This wrapper delegates to the installed `parishkit-create-ministry-rosters`
command. The implementation is added in the create-ministry-rosters migration
phase.

Current skeleton status: only `--version` is expected to succeed until this
command is implemented.

## Planned Usage

```sh
parishkit-create-ministry-rosters --config example-config.yaml --dry-run
```

Keep ParishSoft and Google credentials outside git.
