# Stewardship Phase 2 execution checkpoints

The [controlling plan](../plans/stewardship/overall.md#phase-2-source-truth-initial-setup-and-campaign-preparation)
owns scope and dependency order. The [coordinating checklist](../tasks/stewardship/overall.md#phase-2-source-setup-and-preparation)
links every owning task list; this guide records implementation evidence rather
than redefining behavior.

## Admission and branch

The owner authorized continuation once PR #21 merged. It merged on September 11,
2026 at 13:54:50 UTC as `48be3666f0c89cc15586cb67465cd1ba0504203c`, after all
[merge-queue CI checks](https://github.com/epiphany40223/parishkit/actions/runs/34605469838)
passed. Gate 1 is released. Branch `pr/stewardship-phase-2` starts at that
refreshed `origin/main` tip.

## Active checkpoint

DAT-03 storage is complete; BG-01 is the next dependency-ready package. The
first internal checkpoint implements normalized
content-addressed payload tables and snapshot membership maps, server-clock
task/source fencing, bounded staging, database-verified completeness and
relationship evidence, atomic promotion/reconciliation, immutable manifests and
protected reads. Its source-specific PostgreSQL suite passes all 46 tests,
including migration reversal/reapplication; pure canonicalization/lease tests
pass all 33 cases. The complete baseline passes 2,743 tests; Ruff, formatting,
Markdown and migration drift checks pass. At that checkpoint, no Phase 2 task
was complete yet:
retention anchors/services, daily-fact storage, concrete promotion effects and
runtime/refresh/setup consumers still need their owning implementations.

The next internal checkpoint adds deterministic UTC retention anchors, explicit
parent pins, protected-reader/late-pin race handling, bounded source compaction
and permanent count/cutoff evidence. Source promotion and compaction use the
shared typed audit helper without logging source field values. All 63 source
PostgreSQL cases and all 44 pure source cases pass; the final audit-specific
repeat passes 34 PostgreSQL cases. The updated baseline passes 2,754 tests.
DAT-03.01-.05 are complete for their storage scope. Daily-fact storage,
fact-specific tests and concrete runtime consumers remain open, so DAT-03 as a
whole is not yet marked complete.

The third checkpoint completes daily-fact storage: immutable exact-input graph
generations, SQL completeness and provenance checks, non-regressing interactive
pointers, explicit retained-parent/source pins and shared locks through lazy
reads. The input key includes the campaign-local through-date required by the
graph's today bound: midnight cannot reuse yesterday's dates merely because
source and submission versions did not change. Historical facts use permanent
source metadata; current-scope generations pin their reconstructable source.

Durable rebuild demand implements the five-second debounce and thirty-second
cap. Claims freeze their own revision; concurrent events retain an independent
pending window through completion and abandoned-work recovery. Exact exports
use the generation API without consuming interactive demand. Bounded fact
compaction preserves current/building/failed/claimed/pinned/actively read
generations, deletes whole disposable generations atomically, releases only
their source pins and keeps immutable generation-key/count evidence and audit.
Shared task ownership now takes the retry-root lock before its execution row.

All 38 fact PostgreSQL tests pass, including migration reversal/reapplication,
raw-SQL tampering, failed-build recovery, interrupted cleanup, active lazy
readers and both late-pin race orders. The final combined source/fact/TaskRun
regression passes 165 cases; pure fact/lease validation passes 47 cases. The
baseline passes 2,788 tests. These are internal storage APIs, not enabled report
workers: BG-01/BG-05 own concrete runtime admission, source producer wiring and
queue consumers; RPT-02/RPT-03 retain calculation/materializer/UI ownership.
Runtime database grants remain closed until their owning service is admitted.

BG-01 has started with the internal durable hint dispatcher and task scan.
The transport-facing identity is only a TaskRun UUID; its type and handler
are resolved from durable state and the startup-owned registry. Queue isolation
does not authorize work. Claim, heartbeat, progress and verified outcomes repeat
the owning admission check under retry-root/task locks. Execution occurs outside
a transaction; an unexpected exception or return never implies completion or
safe retry. Recovery fences expired owners and applies only an explicit verified
disposition, preserving unresolved work and retry delay.

The bounded keyset scan repeats lost hints without changing durable task state
and advances across held work so an ineligible prefix cannot starve later work.
Nine PostgreSQL tests and sixteen pure tests pass for this initial substrate.
The dispatcher/scanner are not an enabled runtime service. Singleton scheduling,
Celery/Valkey transport, concrete domain admission, worker lifecycle and task
status APIs remain BG-01 work; all BG-01 checklist items remain open.

The next BG-01 checkpoint adds a PostgreSQL session-pinned singleton scheduler
guard and the closed Celery/Valkey transport factory. Reconnects invalidate old
ownership; transport failures advance fair paging without removing durable
work. Celery 5.6.3/Kombu 5.6.2 are validated locally. The factory uses JSON only,
no result backend or remote control, finite transport timeouts and a single
UUID-only task, following the [Celery configuration reference](https://docs.celeryq.dev/en/stable/userguide/configuration.html).
App-local task registration, service-specific default queues and independent
unacknowledged-message keys prevent one service from inheriting another's handler
or consuming its queue by default. Broker passwords remain separate in-memory
options rather than URL components; ambient Celery overrides fail closed.

All 20 dispatcher/scanner/scheduler/consumer PostgreSQL tests pass, as do nine
broker and sixteen dispatcher pure tests. The baseline passes 2,813 tests.
These factories have not yet been enabled by operational runtime: service
mounts, SQL grants, Valkey ACL provisioning, concrete owning admission and
bounded worker heartbeat/shutdown still need integration and container tests.

The broker isolation checkpoint adds a pure queue inventory and explicit
Valkey ACL builders for the scheduler and each consumer identity. The scheduler
may publish but cannot consume or delete queue data; each consumer sees only
its own normal/restore queues and unacknowledged-message keys. None can read
web login counters or administer Valkey. Seven opt-in tests against a fresh
disposable pinned Valkey container pass, exercising real Kombu publication,
receipt, visibility recovery, requeue and acknowledgement plus server-enforced
cross-service denials. Thirty-eight pure broker/dispatcher/ACL tests pass.
This validates the policy and transport, not yet deployment provisioning or
an enabled worker process.

The worker-lifetime checkpoint adds twenty-second renewal on an independent,
short-lived SQL connection, with finite connection/lock/statement timeouts.
Task and optional exact source leases renew atomically; renewal failure blocks
further execution boundaries without inventing a task outcome. Graceful stop
prevents new claims/external units but allows a verified current unit to finish.
Every handler exit drains its renewer. The scheduler retains its actual owning
SQL session across passes and stops publishing the remainder of a page on drain.

Closed process helpers now exercise Celery's real single-execution controller
without gossip, mingle, broker heartbeat, remote control, CLI banners or forked
workers. The stop event is shared with dispatch, and the controller's current
app is scoped to its lifetime. The nine real Valkey tests include actual worker
consumption/acknowledgement and idle SIGTERM shutdown. Thirty PostgreSQL cases
and nineteen new pure lifetime/process cases pass; the full baseline passes
2,837 tests. Deployment still does not launch these helpers: concrete domain
admission, isolated SQL grants/mount provisioning and runtime entry-point wiring
remain in progress before BG-01 can be marked complete.

The admission checkpoint adds fresh transactional campaign checks using the
existing lifecycle policy and durable restore, purge, go-live and rehearsal
epoch state. Source refresh is the explicit cleanup/pause exception and remains
bound to the current campaign's giving window. Compiled campaign handlers enter
their owning scope before task/domain locks at scan, claim, renewal, recovery
and each durable effect. Admission rejects a missing lock order instead of
quietly acquiring it too late. Unrelated tasks retain independent retry-root
locks; no global task-allocation mutex was added. Raised gate denials advance
the scheduler's fair cursor just like an explicit refusal.

All 255 selected PostgreSQL source/fact/task/admission/worker/campaign-race cases
pass, including the existing unrelated-enqueue concurrency tests and the new
claim-versus-cleanup race. Forty-three pure admission/dispatch/lifetime/process
cases pass. Concrete source request binding, operational exception owners,
phase/status APIs and isolated deployment wiring remain open; these internal
admission services are not HTTP authorization or completion evidence.

The progress/status checkpoint adds closed typed task phases, claim resets,
SQL-enforced phase/history binding and refusal of populated history downgrades.
Admin-only bounded JSON endpoints expose whitelisted task metadata and paginated
immutable history; no worker arguments, exceptions, credential values or domain
payloads are serialized. Fresh authorization is repeated at the response
boundary, and passive polling does not renew an abandoned session's idle timer.
All 90 PostgreSQL task/status/history cases pass, including role denial,
revocation, filtering, privacy and migration tests. The full baseline passes
2,849 tests, and lint, formatting and migration-drift checks pass. ADM-03 still
owns the visible background-work interface; runtime integration remains open.

The broker-provisioning checkpoint adds immutable per-identity Valkey path
references and fresh, resumable allocation of independent web/worker/scheduler
passwords. The private server ACL contains only their hashes and the previously
tested isolated command/key rules. Path validation also reserves future SQL
credential identities, preventing later consumers from inheriting an alias.
No provider credentials or future mail/backup broker accounts are created.
All 180 selected configuration/provisioning tests and the 2,862-test baseline
pass. Existing runtime artifacts are never overwritten as an upgrade shortcut;
the worker/scheduler entry-point and concrete source-handler integration remain
open before enabling those services.

The task SQL checkpoint provisions independent scheduler/worker logins and
closed task-only grants. The scheduler can enqueue and lock/scan work but not
claim or transition it; the worker can update fenced task metadata without
campaign configuration, session or provider credential authority. Audited writes
have only the narrow identity/default-column reads their triggers and INSERT
RETURNING require, not access to historical private contexts. Concrete source
owners must extend their table vocabulary explicitly. Eighteen real PostgreSQL
grant tests, 101 initial selected runtime tests and the 2,867-test baseline pass.
The default background reserve accounts for all installer connections plus the
worker's main/renewal pair and scheduler's pinned session through rollout overlap.
These identities do not yet launch an operational worker or enable source I/O.

The complete source/setup/configuration batch will receive at least three
independent review/fix rounds and passing local/PR CI before human merge
approval. Normal validation uses synthetic data and fake providers. Later
Family response, production delivery, publication, backup/restore and destructive
workflows retain their controlling-plan owners.
