# Campaign boundary processing

[Coordinating tasks](../tasks/stewardship/overall.md#phase-4-production-scheduling-and-delivery) ·
[BG-02 plan](../plans/stewardship/background-processing.md#bg-02-campaign-boundary-occurrences) ·
[Boundary contract](../specs/stewardship/background-processing/spec.md#campaign-lifecycle-boundaries)

## Scope

Branch `pr/stewardship-campaign-boundaries` starts from verified PR #31 merge
`f4e000c5b3f7024e47c7f6d3dbdd30c6cd4976e1` on refreshed `origin/main`, after
[complete protected delivery](stewardship-delivery-reviews.md#protected-delivery).
Deliver BG-02's Phase 4 start/close behavior as one coherent scheduler/worker
increment: durable occurrence production, compiled admission and execution,
ordered overdue recovery, end-date replacement and their real database/runtime
tests. Individual records or helpers are internal checkpoints, not PRs.

BG-02.03 retains shared restore/reopen token preparation in Phase 6. BG-03/04
retain actual Production cleanup and schedule fulfillment; BG-06 retains mail
dispatch and ADM-05 retains activation. Do not expose those unfinished owners
or weaken existing held-work checks to make this slice runnable. Full affected
mail reconciliation remains BG-04; boundary integration must preserve its
existing conservative admission until that owner is ready. Gate 3 remains
after complete Phase 4/5 integration.

## Internal checkpoints

1. Connect the existing ordered lifecycle journal to bounded durable occurrence
   production and the compiled scheduler/worker registry. Use stable identities,
   authoritative database time, current campaign/mode/gate admission and the
   existing TaskRun lease/recovery substrate. Broker hints remain non-authoritative.
2. Complete transactional start/close execution, exact proof and audit metadata.
   Close-first delivery applies any overdue start in the same transaction, with
   no externally visible active gap and no out-of-interval Family access.
3. Reconcile end-date changes with safe queued-work replacement and current
   worker exclusion. Closing first leaves the change to the guarded reopen
   owner. Preserve complete schedule reconciliation and provider-uncertainty
   blockers; do not introduce a partial date-only escape path.
4. Prove duplicate/restart/DST/exact-boundary behavior, missing/stale/foreign
   claims, crash-before/after domain commit, delayed hints, held gates and real
   races. Verify restricted SQL roles, metadata-only scheduler behavior and
   runtime registry wiring without provider credentials or live external writes.
5. Audit any fresh-install SQL/model deltas without retained-database deletion.
   Run repository and integration validation; complete three dual-source
   review/fix rounds and final-head CI before protected delivery.

## Evidence

Planning and implementation have started; no BG-02 task is newly complete.
Existing boundary/storage race tests are prior substrate evidence, not proof
of the new compiled scheduler and worker integration.

The first internal checkpoint implements bounded occurrence/root production and
the compiled metadata/execution/recovery handler. Seventeen PostgreSQL tests
passed in 22.88 seconds, covering exact dates, repeated scans/restart, held
configuration, close-first execution, late-denial rollback, stale/unbound task
views, and recovery before versus after the domain commit. Ruff passes for the
new modules and tests. No runtime registry or additional SQL authority is
enabled yet; restricted-role integration, replacement, audit/lag evidence,
broader races and the complete three-round review/CI cycle remain required.

The restricted-role checkpoint passes 38 PostgreSQL tests in 30.97 seconds.
Actual scheduler/worker logins produce and execute ordered boundaries, including
a populated Family login whose session is revoked and link destroyed at close.
Worker SQL cannot read token ciphertext or session keys; populated premature
lifecycle/scrub attempts fail for both installed and custom worker role names.
Empty-table updates are explicitly distinguished from populated row authority.

An independent fresh database loaded from exact merged PR #31 was compared with
the working fresh-install schema. Its original fingerprint matched before the
comparison. Only three boundary proof functions, four boundary guards and the
narrow `stewardship_setup_completion_write_v1` exception differ; all relations,
columns, constraints, indexes and policies are unchanged. The audited fixture
now contains 338 functions and 337 triggers. No retained database was deleted or
upgraded. This is an internal checkpoint, not completed BG-02 acceptance.

## Runtime and timing checkpoint

The scheduler now registers metadata-only boundary admission and scans the
boundary producer independently of the other producers. The general worker
registers the compiled executor; mail dispatch does not. Every ordinary pass
retains current YAML/SQL authority checks. Runtime assembly, producer isolation,
grant contracts and context-validation tests pass (199 tests in 1.12 seconds).

Terminal boundary changes append a closed `boundary` audit context containing
the occurrence identity, kind, intended/actual UTC Unix microseconds, lag in
microseconds, previous/new state and the event's correlation ID. Skipped and
successful outcomes both retain this context. No parishioner values are allowed
in this schema. Scheduler lag exceeding the existing process-health threshold
of 90 seconds records one durable WARNING per occurrence; its task context
contains the root ID and lag seconds in `count`. The insert-only warning survives
duplicate scans/restarts without granting log-payload reads. BG-10 still owns
notification delivery and escalation.

End-edit admission now checks both execution-bound task IDs and immutable root
allocation keys, rejecting running/abandoned close work even before its worker
binds the occurrence. Queued work remains replaceable. This does not loosen
affected-mail reconciliation or permit edits after the original closing instant.

The complete focused boundary set passes 49 PostgreSQL tests in 38.65 seconds:
production/execution, exact grants, populated credential cleanup, typed timing
audit, lag threshold/deduplication, pre-binding end-edit exclusion, concurrent
workers, and spring/fall DST intervals. Fifty-four lifecycle, work-admission,
exceptional-end and strict schema/model regressions pass in 32.67 seconds.
Ruff lint/format, Markdown lint of this guide and `makemigrations --check
--dry-run` pass. The independent PR #31 catalog comparison was repeated: beyond
the earlier worker-proof changes, only boundary audit, safe-context validation,
end-edit admission, and the two closed audit/operational constraints changed.
No table, column, index or policy was added or changed.

The full credential-free baseline passes: 5,539 tests, 3,477 opt-in/profile
skips, and two pre-existing client-library deprecation warnings in 55.55 seconds.
This is not a claim that skipped database, browser or Compose suites passed.

An additional setup-heavy regression invocation was interrupted after 15 passed
tests in 525.91 seconds, while waiting in a deliberate threading wait. It is
not complete validation or a demonstrated deadlock. Remaining setup regressions
must run in bounded diagnostic groups before final acceptance.

## Approved execution-revision contract

The human approved support for A → B → A with immutable replacement history and
a fresh execution revision for the reused date. The normative data/background
specifications now define monotonically increasing per-campaign/kind execution
revisions, with distinct occurrence IDs and task roots. This is an expressly
approved change to the previously reviewed date-only identity, not permission
to rewrite terminal history or add pre-production upgrade compatibility.

The implementation now atomically retires an obsolete close occurrence and
allocates its successor during the end-date configuration transaction. Both
the producer and executor select the latest execution revision; stale hints
acknowledge cancellation without reviving history. SQL independently enforces
sequential revisions, immutable identity, no competing pending predecessor and
current-revision worker proof. A close that wins before publication of an
earlier reviewed end edit leaves the campaign closed and requires reopening.

The expanded boundary/exceptional-date/regression set passed 77 PostgreSQL tests
in 59.34 seconds; the final six end-date tests passed in 14.51 seconds. After
the independent schema audit, the strict fresh-schema/model and end-date set
passed 23 tests in 25.21 seconds. The latest credential-free baseline passed
5,539 tests with 3,480 opt-in/profile skips and two pre-existing warnings in
56.14 seconds. The schema audit confirmed only the approved execution-revision
column, revision constraints/identity index and associated guard changes beyond
the already recorded boundary deltas. No retained database was upgraded/deleted.

Complete remaining runtime/regression validation and three dual-source review
rounds before PR delivery. No new BG-02 checkbox is complete and this branch
has no PR yet.
