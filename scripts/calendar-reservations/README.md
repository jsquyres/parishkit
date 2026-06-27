# parishkit-calendar-reservations

Check Google Calendar reservations for configured conflicts and domains.

This wrapper delegates to the installed `parishkit-calendar-reservations`
command. The implementation is added in the calendar-reservations migration
phase.

Current skeleton status: only `--version` is expected to succeed until this
command is implemented.

## Planned Usage

```sh
parishkit-calendar-reservations --config example-config.yaml --dry-run
```

Store Google credential files outside git, such as under
`/opt/parishkit/credentials/`.
