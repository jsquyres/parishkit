# parishkit-sync-ps-to-cc

Synchronize ParishSoft contacts to Constant Contact lists.

This wrapper delegates to the installed `parishkit-sync-ps-to-cc` command.

## Usage

```sh
parishkit-sync-ps-to-cc --config example-config.yaml --dry-run
```

Mappings live in YAML under `sync_ps_to_cc.lists`. The command resolves desired
Constant Contact list membership from ParishSoft member workgroups, filters
contacts that have unsubscribed in Constant Contact, computes an action list,
and writes through the shared Constant Contact client unless `--dry-run` or
`--no-sync` is enabled.

Keep ParishSoft, Constant Contact, and email credentials outside git.

## Credential Smoke Test

Automated tests mock Constant Contact writes. Use the documented Constant
Contact authorization flow to create local token files, then run this command
with `--dry-run` first. Dry-run still reads Constant Contact and ParishSoft but
does not write contacts or send notifications.
