# Administration portal tasks

[Task index](README.md) · [Implementation plan](../../plans/stewardship/admin-portal.md) ·
[Normative specification](../../specs/stewardship/admin-portal/spec.md) · [Milestones](milestones.md)

Each task maps to the same numbered item in its linked work package. Read that
item in full: the short label below does not replace its requirements or tests.
Follow the [execution and completion rules](README.md#execution-and-completion).

## ADM-01: Login, denial, and unconfigured-state routing

Scope and dependencies: [ADM-01 work package](../../plans/stewardship/admin-portal.md#adm-01-login-denial-and-unconfigured-state-routing).

- [x] ADM-01.01 — Build Google login, callback, logout, and denial pages.
- [x] ADM-01.02 — Gate all Admin routes on current authorization and state.
- [x] ADM-01.03 — Handle unconfigured and maintenance states.
- [x] ADM-01.04 — Audit login, logout, timeout, and revocation.
- [x] ADM-01.05 — Test direct routes and partial endpoints.

Evidence: Phase 1B implements Google-only initiation/callback, CSRF logout,
retryable denial, current-role checks and durable login/session audit. Real
PostgreSQL and synthetic signed Google tests cover normal and denied claims,
revocation, cookie isolation, expiry and recovery boundaries. Setup/maintenance
routing and direct HTML/POST admission pass ten additional PostgreSQL cases.
The actual wizard and its durable configured marker stay with ADM-02; absent
marker providers fail closed. See [Phase 1B evidence](../../guides/stewardship-phase-1b.md).

## ADM-02: Bootstrap command and transactional setup wizard

Scope and dependencies: [ADM-02 work package](../../plans/stewardship/admin-portal.md#adm-02-bootstrap-command-and-transactional-setup-wizard).

- [ ] ADM-02.01 — Implement bootstrap configuration and every required keyring.
- [ ] ADM-02.02 — Implement isolated temporary setup staging.
- [ ] ADM-02.03 — Implement heartbeat-aware setup progress and watchdog.
- [ ] ADM-02.04 — Expire aborted staging and reject late worker completion.
- [ ] ADM-02.05 — Finalize secrets, YAML, source, and campaign setup coherently.
- [ ] ADM-02.06 — Test wizard aborts, concurrency, and installer recovery.

Evidence: Bootstrap and independent keyring preparation are implemented and
covered by Phase 2 offline/database tests. Original-login public wizard forms
and private logo staging now pass 73 focused cases with 98% coverage and 42 new
browser cases. Scheduler expiry clears public values atomically and fences
original-session artifacts. Sealed setup credential intake, staged source work,
delivery checks and final configured-marker activation remain open.
See [Phase 2 evidence](../../guides/stewardship-phase-2.md).

## ADM-03: Navigation, dashboard, indicators, and configuration

Scope and dependencies: [ADM-03 work package](../../plans/stewardship/admin-portal.md#adm-03-navigation-dashboard-indicators-and-configuration).

- [ ] ADM-03.01 — Build role-filtered navigation and dashboard.
- [ ] ADM-03.02 — Build persistent operational-state banners.
- [ ] ADM-03.03 — Build presence and background-task indicators.
- [ ] ADM-03.04 — Build durable configuration, Ministry activity, and credential editors.
- [ ] ADM-03.05 — Keep Parish-timezone edits prospective.
- [x] ADM-03.06 — Build branding previews and variant handling.
- [ ] ADM-03.07 — Test configuration UI, Ministry activity, concurrency, and timezone isolation.

Evidence: In progress. The Ministry activity and Parish profile editors use
signed exact previews and durable Applying/Applied configuration requests;
42 PostgreSQL cases cover required fields, source/configuration changes,
permissions, restricted web grants, installation, retry, and campaign-timezone
isolation. Navigation, Testing banners, passive Family-presence/background
indicators and HTML task history now pass PostgreSQL and three-engine browser
tests. Integration settings now use the same exact-preview protocol; fresh-Admin
credential intake seals to the target installer, with immutable provider scope,
bounded authentication checks and passive request progress. Its 45-case HTTP/
form run has 93% focused coverage, and 30 new three-engine browser cases pass.
Normalized logo upload, four-size preview, immutable activation and historical
branding are implemented. Durable, bounded worker cleanup preserves all retained
references and resumes interrupted removal; the combined branding/history run
passes 68 cases with 95% focused coverage. Post-install selection now requires
the latest target receipt, complete consumer acknowledgements and matching public
provider scope; the combined 93-case run has 94% focused selection coverage.
Wizard finalization, explicit delivery tests and full acceptance checks are not
complete. See
[Phase 2 evidence](../../guides/stewardship-phase-2.md#worker-composition-and-initial-admin-editors-in-progress).

## ADM-04: Campaign editor, content, schedules, and previews

Scope and dependencies: [ADM-04 work package](../../plans/stewardship/admin-portal.md#adm-04-campaign-editor-content-schedules-and-previews).

- [ ] ADM-04.01 — Build guarded campaign creation and cloning.
- [ ] ADM-04.02 — Build structural campaign configuration forms.
- [ ] ADM-04.03 — Build named content and email-template editors.
- [ ] ADM-04.04 — Build page previews and readiness-test emails.
- [ ] ADM-04.05 — Build atomic schedule reconciliation previews.
- [ ] ADM-04.06 — Test campaign editing, previews, and schedule races.

Evidence: In progress. New-draft creation and structural editing now use
actor/configuration/source/runtime-bound exact previews and Applied receipts.
The editor covers dates, timezone, modules, current Ministry/fund selections,
financial/comparison periods, additional information and structural read-only
states. Combined form/editor/navigation tests pass 85 cases with 98% focused
coverage; the expanded browser suite passes 135 cases across three engines.
Named page slots and independent email revisions now have visual/source/plain-text
editors and sanitized fictional before/after previews. Exact requests reconcile
existing template consumers and preserve immutable YAML/projection history;
content form/view integration coverage is 92%. Combined schedule/draft-date
reconciliation now passes 70 tests with 94% schedule-module coverage; exact
work previews, explicit removals and timezone-bound revisions preserve SQL
admission. Archived campaign cloning now has exact previews, fresh child IDs and
explicit new-date/current-fund entry; its combined run passes 44 tests with 91%
focused coverage and eighteen selected browser cases. Read-only retained content
previews preserve the campaign's selected configuration, Parish name and logo.
Readiness-test mail and
complete integration/regression/review acceptance remain open.
See [Phase 2 evidence](../../guides/stewardship-phase-2.md#immutable-content-and-template-editing).

## ADM-05: Production transition and pre-start withdrawal

Scope and dependencies: [ADM-05 work package](../../plans/stewardship/admin-portal.md#adm-05-production-transition-and-pre-start-withdrawal).

- [ ] ADM-05.01 — Build go-live readiness and exact impact preview.
- [ ] ADM-05.02 — Build transition requests, rehearsal invalidation, and cleanup controls.
- [ ] ADM-05.03 — Build atomic Production confirmation with asynchronous catch-up progress.
- [ ] ADM-05.04 — Build guarded pre-start withdrawal.
- [ ] ADM-05.05 — Test cleanup, readiness, and campaign-boundary races.

Evidence: Not started.

## ADM-06: Restore release, delivery pause, reopen, and archive

Scope and dependencies: [ADM-06 work package](../../plans/stewardship/admin-portal.md#adm-06-restore-release-delivery-pause-reopen-and-archive).

- [ ] ADM-06.01 — Build state-aware restore inventory, fresh-token preparation, and release.
- [ ] ADM-06.02 — Build delivery pause, resume, and post-close resolution.
- [ ] ADM-06.03 — Build staged token preparation and guarded campaign reopen.
- [ ] ADM-06.04 — Build archive, unarchive, Return, and obligation resolution.
- [ ] ADM-06.05 — Test lifecycle races and durable post-close coverage.

Evidence: Not started.

## ADM-07: User rules and Ministry assignments

Scope and dependencies: [ADM-07 work package](../../plans/stewardship/admin-portal.md#adm-07-user-rules-and-ministry-assignments).

- [ ] ADM-07.01 — Build login-rule tables with serialized autosave and conflict recovery.
- [ ] ADM-07.02 — Implement low-friction role edits and high-impact notifications.
- [ ] ADM-07.03 — Build chair suggestions, grant provenance, and inherited-role review.
- [ ] ADM-07.04 — Build manual assignment and runtime-suspension review.
- [ ] ADM-07.05 — Test rapid autosave, uncertain outcomes, precedence, and policy races.

Evidence: Not started.

## ADM-08: Manual refresh, follow-up queues, and logs

Scope and dependencies: [ADM-08 work package](../../plans/stewardship/admin-portal.md#adm-08-manual-refresh-follow-up-queues-and-logs).

- [ ] ADM-08.01 — Build coalesced manual refresh controls.
- [ ] ADM-08.02 — Build additional-information and manual-census queues.
- [ ] ADM-08.03 — Build scoped Ministry follow-up controls.
- [ ] ADM-08.04 — Build searchable Admin logs and timezone-aware exports.
- [ ] ADM-08.05 — Test workflow history, scope, and concurrency.

Evidence: Not started.

## ADM-09: Census review and ParishSoft publication UI

Scope and dependencies: [ADM-09 work package](../../plans/stewardship/admin-portal.md#adm-09-census-review-and-parishsoft-publication-ui).

- [ ] ADM-09.01 — Build bulk proposal review, edit, accept, and ignore.
- [ ] ADM-09.02 — Separate review decisions from publication execution.
- [ ] ADM-09.03 — Build source preflight, conflict resolution, and progress.
- [ ] ADM-09.04 — Preserve original submitted values beside Admin edits.
- [ ] ADM-09.05 — Test publication authorization, subsets, and stale plans.

Evidence: Not started.

## ADM-10: Exceptional campaign purge web workflow

Scope and dependencies: [ADM-10 work package](../../plans/stewardship/admin-portal.md#adm-10-exceptional-campaign-purge-web-workflow).

- [ ] ADM-10.01 — Build purge eligibility and durable request UI.
- [ ] ADM-10.02 — Build campaign quiescence and conflicting-work resolution.
- [ ] ADM-10.03 — Build inventory, backup creation/revalidation, and recovery-evidence controls.
- [ ] ADM-10.04 — Build fresh-authentication and typed purge confirmation.
- [ ] ADM-10.05 — Build reader-drain status, pre-delete recovery, deletion retry, and terminal UI.
- [ ] ADM-10.06 — Test every purge state, race, and confirmation boundary.

Evidence: Not started.
