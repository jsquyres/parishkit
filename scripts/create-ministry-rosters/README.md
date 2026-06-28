# parishkit-create-ministry-rosters

Create ministry rosters from ParishSoft data and write them to Google Sheets.

This wrapper delegates to the installed `parishkit-create-ministry-rosters`
command.

## Usage

```sh
parishkit-create-ministry-rosters --config example-config.yaml --dry-run
```

Roster mappings live in YAML under `create_ministry_rosters.ministries` and
`create_ministry_rosters.workgroups`. Each target writes a table to Google
Sheets. Ministry targets can also define `role_sheets` that write a filtered
roster for specific ParishSoft ministry roles.

Keep ParishSoft and Google credentials outside git.

## Google Credential Smoke Test

Automated tests mock Google Sheets writes. To verify real credentials, run a
read-only Sheets smoke test manually:

```sh
scripts/smoke-tests/google-api.py \
  --service sheets \
  --version v4 \
  --scope https://www.googleapis.com/auth/spreadsheets.readonly \
  --service-account-file /opt/parishkit/credentials/google-service-account.json \
  --delegated-subject admin@example.org \
  --spreadsheet-id example-spreadsheet-id \
  --send
```
