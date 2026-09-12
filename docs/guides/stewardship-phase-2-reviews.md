# Phase 2 review ledger

This ledger follows the [delivery cycle](../plans/stewardship/overall.md#automated-phase-delivery-cycle)
and [Phase 2 scope](stewardship-phase-2.md). Raw review outputs remain local,
not repository content. Neither a correction checkpoint nor an interim review
completes Phase 2 acceptance or authorizes merging.

## Round one: interim source/setup correction pass

Reviewed commit: `1619866414d04a33d57f71e4e55524b49371ad49`.
Base: PR #21 merge `48be3666f0c89cc15586cb67465cd1ba0504203c`.
Session: `20260912-125902-d5675a`.
All 26 Pika-generated Claude shards and the single detached Codex reviewer
completed successfully. Finalization has no failed agents, degradation, verdict
mismatch or salvage requirement. The result is **request changes**: 86 retained
findings (six High), comprising one agreed, 84 Claude-only and one Codex-only.

Identifiers below use that finalized bucket order, with each bucket retaining
its emitted order. Review and correction are still in progress. Implemented
corrections awaiting PostgreSQL evidence are not
recorded as validated or as completing a review/fix round.

| ID | Severity | Finding | Current disposition |
| --- | --- | --- | --- |
| 1 | Medium | Undrained renewal is caught as an ordinary broker error | Implemented: fatal drain boundary, explicit 30-second process-drain budget and closed diagnostic. Broker-boundary tests preserve a pre-existing handler exception as context while preventing consumer continuation. |
| 2 | High | One broken task discards the scheduler page and starves later work | Implemented: isolate stale/invariant/missing-object scope failures per row, retain a closed diagnostic and advance the cursor. Database-outage failures remain service-level. PostgreSQL evidence pending. |
| 3 | High | SQL fact liveness argument collides with the fence column | Validated: a forward migration binds positional task/fence/worker arguments. Direct SQL tests reject each mismatched component; recovery tests retain exact ownership. |
| 4 | High | Explicit blank should fall back to an older contact value | Auto-skipped, false-positive: `test_explicit_empty_search_value_does_not_fall_back_to_older_contact_email` explicitly protects a source-cleared email. Missing and verified-blank values are intentionally different; fallback on falsiness would resurrect cleared data. |
| 5 | High | Lost credential-installer interlock rejects the candidate | Implemented: owner-check failures cross a fatal, private-text-free boundary; an already spawned helper is drained. The candidate is neither rejected nor installed. PostgreSQL sealed-intake evidence pending. |
| 6 | High | Giving lookup merges DUID and parish-local Family ID spaces | Implemented: use the existing shared `link_family_pledges`/`link_family_contributions` DUID contract only. Tests cover conflicting local IDs and refuse local-ID fallback for unknown DUIDs. |
| 7 | High | Household fallback omits death date | Auto-skipped, false-positive: the published Family Member-list DTO has no death-date field to copy; the Member detail endpoint returns `MemberSearchResponseDto`, which already includes `dateOfDeath`. Inventing a fallback field does not fix a demonstrated provider path. |
| 8 | Medium | Dashboard failure links open JSON rather than the task page | Implemented: use `background_task_page`; navigation regression pending. |
| 11, 14 | Medium | Same dashboard link | Auto-skipped, duplicate of 8. |
| 12 | Medium | Retained-content view has no request tests | Auto-skipped, false-positive: `test_content_history_postgresql.py` covers actual HTTP, real web grants, archived branding/content, revision scope, empty content, non-Admin refusal and restore hold. |
| 13 | Medium | Credential-selection authorization has only pure helper tests | Auto-skipped, false-positive: `test_integration_selection_postgresql.py` exercises web/installer SQL identities, exact ACK proof, settings/stale-base/freshness refusal, pending replacement, actor isolation and migration replay. |
| 15 | Medium | Source rejection has no takeover/refusal tests | Auto-skipped, false-positive: `test_source_rejection_postgresql.py` covers newer-owner rejection, live external-read hold, idempotent admission, forensic immutability, audit rollback, promotion race and migration replay. |
| 17, 38 | Medium | Configuration unavailability is misclassified as invalid input | Implemented: the shared mapper handles `ConfigError` before its `ValueError` superclass, returning safe 503 plus Retry-After; field errors remain 400. Pure regression passes; HTTP expectations pending. |
| 19 | Medium | Manual source-progress button becomes inert after polling stops | Validated browser correction: preserve the native POST when automatic polling is no longer live. |
| 21 | Medium | Family presence SQL uses the 30-minute Admin idle allowance | Validated: the forward migration uses 60 minutes. Real web-role heartbeat and SQL tests accept 45-minute idle sessions and refuse 61-minute idle sessions without renewing activity. |
| 23 | Medium | Share labels accept controls rejected by the YAML schema | Validated: form uses the same canonical text check; tab, C1 and DEL tests reject the label before candidate construction. |
| 25 | Medium | Same Family presence idle mismatch | Auto-skipped, duplicate of 21. |
| 29 | Medium | Progress HTTP boundary tests run as schema owner | Implemented: hidden-field and watchdog request assertions now use actual web-role grants. PostgreSQL evidence pending. |
| 30 | Medium | Branding preview does not recheck its independently reread YAML base | Implemented: absent or changed base raises staleness before candidate construction. Regression pending. |
| 33 | Medium | Drain exception masks an existing handler exception | Resolved with 1: fatal non-drain must take precedence over an ordinary handler exception; a closed diagnostic is emitted and the original exception remains chained. Both handler-success/failure broker paths pass. |
| 39 | Medium | Optional branding can break error pages when runtime/storage is absent | Validated: catch the explicit limiter and filesystem unavailability classes as well as configuration/database failures. No blanket exception suppression. |
| 42 | Medium | Same optional-branding error boundary | Auto-skipped, duplicate of 39. |
| 47 | Medium | Cancellation can rewrite a completed setup attempt | Auto-skipped, false-positive: the SQL guard prohibits terminal rewrites and currently refuses completion entirely until its finalization owner exists. The proposed intermediate completed-but-bootstrap state is not an implemented transition. Finalization must retain atomic marker ownership. |
| 55 | Medium | Progress docstring implies GET commits expiry | Corrected documentation: GET remains passive; POST commits expiry and the scheduler independently fences abandoned staging. Existing PostgreSQL tests explicitly distinguish both paths. |
| 70 | Medium | `hasMembers` should be boolean | Auto-skipped, false-positive: the published `FamilySearchResponseDto` declares `hasMembers` as int32, unlike the neighboring boolean flags. |
| 79 | Medium | Renewal could return success after a login-binding change | Implemented defensive final binding check; the renewal transaction rolls back if authentication changes the attempt's original session ID. PostgreSQL regression pending. |
| 85 | Medium | Member detail/search DTO equivalence is unsupported | Auto-skipped, false-positive: the published GET Member response and POST Member-search items both reference the exact same `MemberSearchResponseDto`. |
| 86 | Medium | Browser clock skew prematurely stops setup renewal | Validated: render/return server time and advance it using monotonic browser elapsed time. Tests cover clocks 48 hours ahead/behind and a later seven-day wall-clock jump. |

Additional dispositions from the same round (not an additional review round):

| ID | Severity | Finding | Current disposition |
| --- | --- | --- | --- |
| 9, 10 | Medium | Repeated payload parsing and caller-dependent SQL name resolution | Validated: forward migration parses each canonical insert once and pins/qualifies all three source guards. A real PostgreSQL test shadows source relations with temporary tables and still stages against the genuine manifest/lease/payload. Full source reversal/reapply passes. |
| 16 | Medium | Setup SQL events missing from Python vocabulary | Validated: add the five implemented setup events and compare the installed audit function with the enum. The claim that every other SQL event already belonged to this enum was inaccurate, but explicit setup vocabulary is useful. |
| 18 | Medium | Duplicate Family presence section vocabulary | Validated: the model constraint and endpoint derive from the same ordered vocabulary; existing section/SQL tests pass. |
| 20, 26 | Medium | Repeated dashboard configuration hydration | Validated: the dashboard lends its verified projection to presentation-only context processors for that response. No authorization check consumes this hint; no global cache is added. The existing reference-population query budget passes unchanged. |
| 24 | Medium | Automatic header polling writes report-view audit events | Validated: a separate counts-only endpoint shares authorization and final revocation checks, but fetches no task identities and records no report read. Explicit list/detail reads retain audit records. Real web-role and passive-session tests pass. |
| 28 | Medium | Misleading column restriction on public projections | Validated: remove the overridden Parish column map and document the complete read needed for canonical YAML/SQL startup parity. Grants are not broadened; existing private-table and runtime-role tests pass. |
| 32 | Medium | Setup/session deadline copies can drift | Validated: share pure session policy constants and test installed setup guard intervals. Changing policy still requires an explicit SQL migration. |
| 34 | Medium | Missing ParishSoft integration leaks an ORM exception | Implemented: bounded optional fingerprint lookup raises the same scope denial as a changed credential; explicit missing-integration regression pending. |
| 43 | Medium | Stale promotion test fails for missing lock, not changed campaign | Validated: test holds the real work-order lock while deliberately bypassing the service admission already tested separately. Using `execution.effect()` as suggested would fail at that earlier service check and still not exercise SQL. |
| 46 | Medium | Content history retains every full body | Validated: retain a fixed 32-byte canonical-value digest per revision identity instead of references to all bodies. Repeated and mutated revision checks plus database ancestry tests pass. |
| 48 | Medium | Stale credential receipt reported as unavailability | Validated: stale receipt/settings evidence maps to 409. An in-flight replacement remains a retryable 503, not a stale or invalid-input result. |
| 51 | Medium | Inactive selected funds disappear from draft editor | Validated: both pledge and comparison selections retain their inactive, labeled fund; an unrelated draft name edit succeeds under actual web grants. |
| 53, 57 | Medium | Frozen setup supposedly permits transitions and misleading audit events | Auto-skipped, false-positive: `OLD.state='frozen' OR ...` is the condition for raising an exception, not for allowing the update. New PostgreSQL tests reject all three claimed transitions with owner, arbitrary and null attribution and assert no audit event was added. |
| 56 | Medium | Ready generation bypasses demand claim liveness | Validated: check the demand's exact live claim before transfer, even after generation publication. Same-owner replay and abandoned-owner recovery pass; a live rival receives `FactUnavailable`. |
| 59 | Medium | Terminal branding cleanup has no explicit retry path | Implemented: admit explicit retry under existing eligible/unpinned/configuration gates while retaining one automatic root per bundle. Completed-command replay performs no new file mutation. PostgreSQL evidence pending. |
| 65 | Medium | Delta compares raw group names with normalized retained names | Validated: use the full-load scalar canonicalization; whitespace, nonbreaking-space and decomposed-accent regression cases preserve delta equivalence. |
| 67 | Medium | A new configuration hold prevents cleanup failure settlement | Implemented: exact-claim failure acknowledgement does not authorize file IO and can settle after admission closes. PostgreSQL evidence pending. |
| 68 | Medium | Wrong-typed chair identity map looks like missing bindings | Validated: require UUID keys and typed seed identities. A genuinely empty binding map still follows the established fail-closed policy. |
| 69 | Medium | Content reorder can trigger changed-content admission | Implemented: compare ID-keyed records before running mutation gates. Explicit no-current/held reorder regression pending. |
| 73 | Medium | Preview date placeholders use machine-format civil dates | Validated: sample substitution uses the shared civil-date formatter without timezone shifting. Stored templates remain unchanged. |
| 74 | Medium | Retained credential requests select a future emitted parser | Validated: freeze the v6 request's supported public-schema selection. Replay produces the identical candidate even when the current emission selector changes. |
| 77 | Medium | Partial stdin write can stall provider validation | Validated: one bounded private pipe exchange runs while the supervisor checks ownership, then must be killed/reaped/joined before descriptors close. Reserve drainage in the request TTL. A real offline subprocess delays reading a pipe-capacity-exceeding payload and completes; 55 provider tests pass. |
| 80 | Medium | Credential filesystem permission error becomes an ordinary source hold | Auto-skipped, false-positive: `SourceCredential.read()` delegates to `read_private()`, which converts every filesystem `OSError`, including `PermissionError`, to a closed `CryptographicError` before this classifier. |
| 82 | Medium | Exhausted shared retries skip source failure classification | Validated: unwrap bounded/cycle-checked retry wrappers before all classification branches and recognize shared transient transport types. Unknown ownership/drain failures remain unclassified. |

Provider contract evidence was checked on September 12, 2026 against the
[published v2 OpenAPI document](https://ps-fs-external-api-prod.azurewebsites.net/swagger/v2/swagger.json).
The raw provider schema is not committed. Giving identifier semantics follow
the existing shared ParishKit linking functions rather than an inferred local-ID
alias based only on the provider's inconsistent field capitalization.

Further dispositions and corrections from the same round:

| ID | Severity | Finding | Current disposition |
| --- | --- | --- | --- |
| 22 | Medium | New ancestry queries hardcode model identifiers | Validated: content/Ministry queries derive quoted tables and columns from model metadata while binding all submitted values. Existing PostgreSQL retained-content and identity tests pass. |
| 27 | Medium | Recovery repeatedly reloads the same request and lease | Validated: a call-local lazy evidence object shares immutable observations only during one locked decision. New-work admission retains its independent authorization read. SQL query bounds and stale-after-transition refusal pass. |
| 31 | Medium | Presence uses the work-order lock | Retained with documented invariant: mode/epoch, Family eligibility and source-name lookup must form one observation. Plain READ COMMITTED does not provide it. Pages remain bounded; concurrent mixed-load evidence is still required by ARC-08, not inferred from a population-size test. |
| 35 | Medium | Compaction orphan discovery can scan retained payload history | Operational integration remains open under OPS-07.02/.05. Deleting only payloads from this call's removed memberships, or skipping empty membership batches, would strand older orphans when the payload deletion limit is reached. No compaction runtime is enabled in Phase 2; the later owner must bound discovery as well as deletion and prove residual cleanup. |
| 36 | Medium | Per-row source guards may be costly at scale | Corrected repeated dynamic planning with nine static typed lookups; each inserted row still checks the wall-clock Task/source lease. A real PostgreSQL benchmark stages 18,000 payloads/memberships in 500-row batches within a 30-second total and 10-second batch bound. The 33-case storage/credential batch passes. This is storage evidence, not the remaining complete provider/Compose import demonstration. |
| 37 | Medium | Tenant revalidation failure does not trigger full fallback | Auto-skipped, already handled by fail-closed tenant admission: a key no longer proving the expected organization cannot authorize a larger full read. Feed ambiguity is distinct from credential/tenant failure. Clarified the shared API contract and added a real coherent-client regression proving no subsequent collection fetch. |
| 40 | Medium | Historical content and work-hold admission lack tests | Validated: real archive/Return-to-Testing fixtures test absent/different current ownership, then isolate a real preparing work gate. Guards remain enabled. |
| 41 | Medium | Held abandoned source roots repeatedly publish hints | Validated: abandoned recovery hints require an actionable current recovery plan. Expired running claims still receive hints so SQL can fence them. A reserved external-read deadline suppresses publication until drainage is proved. No task history/deadline is rewritten merely to throttle hints. |
| 44 | Medium | Recent retention anchors become a large in-memory ID exclusion | Validated: filter the recent interval in SQL before calculating older anchors and candidates. Retention/race tests pass, including exact inspected metadata population. |
| 45 | Medium | Temporarily unavailable branding/credential dependencies permanently fail configuration | Validated: typed readiness unavailability leaves the same request retryable with no failed checkpoint. Actual writing-to-ready branding and later successful installation pass. |
| 49 | Medium | Outcome predicates could use a dispatch mapping | Auto-skipped, negligible impact: no incorrect action/state outcome was identified. A second mapping/function layer is not required for correctness; bounded proof sharing and explicit recovery-hint handling address the concrete defects without changing the default-deny policy. |
| 50 | Medium | Dashboard holds work serialization through template rendering | Validated: retain coherent bounded database observation and audit under the work lock, then release it before rendering. Final authorization runs after rendering. Tests inspect the backend lock inventory and refuse a concurrent revocation; the existing 5,000-Family/100-session query and latency baseline passes. This is not a simultaneous mixed-workload claim. |
| 52 | Medium | Credential-selection preview renders under the work lock | Validated: capture exact base/proof under the lock, then construct and render the immutable preview outside it. Real web-role tests inspect the backend lock inventory at both operations. Confirmation still revalidates current evidence. |
| 54 | Medium | Request and attempt SQL duplicate refresh-window derivation | Validated: forward migration makes request admission call the existing window helper, also pins its search path. Installed-function contract and financial/current-scope PostgreSQL tests pass. |
| 58 | Medium | Unknown provider-helper errors reject otherwise valid credentials | Validated: ambiguous adapter/DTO/transport failures report unavailable with no private exception text. Invalid is reserved for malformed candidate input or explicit authentication refusal. Slack and SMTP transient/error responses are distinguished; all 56 provider tests pass. |
| 60 | Medium | Missing or malformed chair tenant settings raise incidental exceptions | Validated: derive the canonical bounded organization before querying, with a closed storage-invariant error for unavailable scope. Missing, wrong-shaped and noncanonical cases pass. |
| 61 | Medium | Credential expiry is based on form-render time and too short for consumer recreation | Validated: the server chooses a one-hour lifetime at first intake under the reservation lock. Exact retries reuse the durable expiry, including after expiry; the five-minute fresh-auth/form-intent limits remain unchanged. The form explains the operator deadline. |
| 62 | Medium | Provider context RLS exempts the table owner | Validated: new migration forces RLS while preserving existing target read/intake policies. Installed flags, actual restricted-role context tests and migration reversal/reapply pass. |
| 63 | Medium | Reserved future Valkey identities differ from currently provisioned services | Auto-skipped, already handled by phase ownership: only implemented web/worker/scheduler services are provisioned and only supplied passwords enter the server ACL. Reserved mail/backup identities are not launched or granted access; their owning phases must add provisioning with real consumers. |
| 64 | Medium | Changed handoff keys block installer startup without a distinct diagnostic | Validated: emit the closed `credential_handoff_key_mismatch` event before refusal, without key values. The installer runbook requires restoring the original matching key; automatic public-key replacement would strand retained ciphertext and is not an authorized rotation protocol. |
| 66 | Medium | Out-of-query contributions reject the whole observation | Retained: the cited uncertainty concerns pledge creation/effective-date semantics, for which the code already avoids date filtering. Contribution query-contract violation cannot prove complete in-window coverage. Silently dropping unexpected records could accept an incomplete observation. Existing tests intentionally refuse ignored contribution filters. |
| 71 | Medium | Roster identities collide for different null-ID roles | Validated in part: a null role ID now falls back to the role name, with regression coverage. End date remains mutable stint content rather than identity; changing it preserves the same row key. Genuine duplicate logical identities still refuse whole promotion instead of silently publishing partial source truth. |
| 72 | Medium | Pin/compaction runtime grants are absent | Auto-skipped for Phase 2, already handled by phase ownership: fact builders/pins and source/fact retention are storage primitives, not registered runtime executors. Actual grants belong with the Phase 4/5 fact/export consumers and Phase 6 OPS-07 compactors. Do not pre-grant PII deletion to the ordinary source worker. |
| 75 | Medium | Unexpected dashboard exceptions expose framework error pages | Auto-skipped, false-positive: the outer security middleware normalizes unmarked framework 500 responses, including DEBUG pages. Prepared configuration validation covers missing projections and zero-denominator percentages are supported. New injected-defect HTTP tests verify the common boundary rather than misclassifying programming errors as ordinary availability failures. |
| 76 | Medium | Scheduler setup guard inspects NEW before rejecting DELETE | Validated defensive forward migration: deletion is rejected first. The real SQL delete regression checks the explicit history message and SQLSTATE 23514. |
| 78 | Medium | Scalar Valkey password paths change meaning during topology generation | Auto-skipped, false-positive: both provisioning and rendering first call `resolve_valkey_files`, which binds the scalar to the original service role and rejects unsupported/ambiguous use before per-service derivation. The finding omitted this normalization. |
| 81 | Medium | Disabling financial resets custom sharing options silently | Validated: the exact change preview explicitly warns that re-enabling starts with defaults; retained configuration history remains untouched. A real HTTP regression confirms warning-before-application and unchanged existing labels. |
| 83 | Medium | Failed/final fact generations have no deletion path | Auto-skipped for Phase 2, already handled by later ownership: OPS-07/DAT-09 must add their exact fenced retention and exceptional-purge disposal rules. Current refusal is intentional until those owners exist, not permission to bypass protected history. |
| 84 | Medium | An abandoned refresh root can absorb manual requests | Retained with clarified semantics: actual running claims, retained source leases and promoted roots are excluded. An abandoned root with none of those remains waiting on its recovery dependency/admission; receipts expose its actual status, not claimed running work. Creating more roots would not resolve that hold. Finding 41 removes repeated broker publication while held. |

The new credential sequencing regression also found and fixed an additional
problem: after a credential was installed/acknowledged but before its fingerprint
was selected in YAML, a second replacement could bind the obsolete YAML
fingerprint as its rollback predecessor. Sealed intake now rejects that second
replacement under the target-reservation lock. The end-to-end test then selects
the first credential, stages/cancels another, and proves cleanup retains the
actual working bytes. Reusing an intake identity with different contents is a
typed invalid request, not transient service unavailability.

Subsequent passing PostgreSQL batches validate the earlier pending entries
2, 5, 8, 17, 29, 30, 34, 38, 59, 67 and 79. Content reorder entry 69 is now
covered with genuine archived history and a work hold. These later results
supersede those rows' earlier pending-evidence checkpoints.

Focused correction evidence includes 76 worker/provider/broker tests, 102 source
giving/loading/corpus/household tests, 38 admin-error/share-form tests and 12
source-progress browser cases across three engines. Later focused suites pass
55 provider tests, 36 delta/failure tests, 53 content/schema-selection tests,
40 chair/failure tests and 32 selection/content-form tests.

The full diagnostic PostgreSQL run reported 1,743 passes and seven failures.
The first correction batch reported 221 passes and four fixture/status failures;
the next reported 79 passes and one incorrectly isolated SQL test. Those
failures were corrected. Subsequent focused PostgreSQL batches pass all 117
source/task/grant/content tests and all 47 setup/progress/campaign-editor tests.
The earlier source/fact/scheduler/branding/progress corrections also passed their
focused cases within those diagnostic batches. Counts overlap and must not be
summed into a full-suite claim. Full post-correction regression and the remaining
triage are still required; this does not complete a review/fix round.

The current full browser run passes all 318 cases across three engines. The
later baseline passes 3,765 tests with 2,150 explicit profile skips and two
existing warnings; it does not replace PostgreSQL/browser/container evidence.
Further focused PostgreSQL batches pass 49 cleanup/selection/presence cases,
48 source-attempt/branding/selection cases, 18 retention/race cases, 33
source-outcome/handoff/content cases, 76 request/attempt/campaign-editor cases,
and 15 dashboard/identity-performance cases. The subsequent full PostgreSQL
run finished with 1,793 passes and five failures: three outdated dashboard-error
assertions and two missing SQL admissions for the new handoff-key diagnostic.
Those are corrected, and the focused rerun passes all 78 cases. These overlapping
focused results do not replace a clean full-suite run or complete a review/fix
round.

## Setup finalization specification decision

The [wizard contract](../specs/stewardship/admin-portal/spec.md#bootstrap-and-first-admin-wizard)
requires cancellation cleanup before the configured marker, including after
authoritative YAML selection. The
[architecture contract](../specs/stewardship/architecture/spec.md#configuration-and-secrets)
previously permitted selected-but-unapplied cancellation only for exceptional
campaign end edits. On September 12, 2026 the owner explicitly approved extending
that journaled exception to initial setup. The specifications and ADM-02 plan now
require exact original-attempt/predecessor binding and atomic database activation
with the configured marker. This decision resolves the specification conflict;
implementation remains open. It does not authorize applied-configuration rollback,
broader credential grants or a setup-completion claim.

### Approved setup cancellation implementation checkpoint

The explicit bootstrap-to-configured intent parser preserves every bootstrap
Administrator and rejects ordinary/default intake, partial profiles, replaced
identities and malformed private values. Its 60-case combined parser regression
passes. SQL now requires an atomic original-attempt/request binding and retains
immutable setup-abort decisions. Selected-candidate recovery checks original
expiry, journals before file restoration, and runs before forward recovery.
The configured-marker/source/Family activation owner remains deliberately closed.

An original-login-only `/admin/setup/cancel` page can cancel finalization across
the selected-but-unapplied mismatch without admitting other configuration edits.
Real web-grant HTTP tests cover passive reads, CSRF, another login, private-value
exclusion and durable cancellation. The restricted configuration installer can
consume that expiry proof without session or source-payload access. Temporary
logos stay pinned through interrupted restoration; actual scheduler/worker tests
prove cleanup after the failed checkpoint and retention when another prepared
configuration still references those assets.

The integrated cancellation/configuration batches pass 74 and 25 cases; the
latest cancellation/HTTP/branding-worker batch passes all 33 cases. Ruff and
formatting pass, and the latest baseline passes 3,792 tests with 2,172 explicit
profile skips and two existing warnings. Counts overlap. Full current PostgreSQL,
browser/container acceptance, remaining wizard work and the phase review rounds
are still required.

### Subsequent regression and credential-intake checkpoint

The complete PostgreSQL regression at the cancellation checkpoint passed all
1,815 tests in 18 minutes, 25 seconds. Later focused runs cover the additional
static source lookup, worker acknowledgement and sealed wizard intake changes;
the full result does not claim to cover code added after that run began.
The source review corrections are committed as cd4ea30.

The worker/scheduler acknowledgement command now checks the already-running
process cohort and actual mounted bytes without manufacturing replacement
receipts. Its restricted-role tests reject stale process evidence and preserve
ciphertext exclusion. The temporary setup-source cryptographic handoff has
original-attempt, credential, Task, worker and source-fence binding; its private
recipient lives only in memory. This primitive is not yet a registered exchange
or setup loader.

Wizard-only credentials now have their own original-login storage and
write-only HTTP forms. They cannot enter the live replacement queue. Collecting
edits use the entire attempt's optimistic version; loading refuses replacement.
Terminal expiry/cancellation atomically clears ciphertext and public provider
settings, retaining only safe receipts and redacted audit events. Web and
scheduler ciphertext reads are denied by column grants; SQL repeats ownership,
fresh-authentication, closed settings and terminal-scrub checks.

The integrated intake/HTTP/cancellation run passed 65 tests with 93% focused
coverage. The later audit/scrub-settings batch passed 35 tests, followed by
68 setup, discovery, credential-isolation and migration cases. Six new
Chromium/Firefox/WebKit mobile/desktop component checks pass. Counts overlap.
After correcting two outdated acknowledgement-grant assertions, the full
baseline passes 3,825 tests with 2,210 explicit profile skips and two existing
warnings. Ruff, formatting and migration-drift checks pass.

The setup exchange/loader, staged campaign, delivery checks, atomic
source/Family/configured-marker activation, final Compose demonstration and
three complete phase review/fix rounds remain open. These checkpoints do not
complete Phase 2 or authorize a merge.
