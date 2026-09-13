# Phase 2 integrated acceptance

[Execution guide](stewardship-phase-2.md) ·
[Controlling phase](../plans/stewardship/overall.md#phase-2-source-truth-initial-setup-and-campaign-preparation) ·
[Milestone status](../tasks/stewardship/milestones.md#phase-2-setup-and-source-truth) ·
[Review ledger](stewardship-phase-2-reviews.md)

This index identifies executable acceptance evidence for the complete Phase 2
batch. The chronological review ledger remains the record of earlier component
checks and corrections; those checkpoints alone do not close this phase.

## Demonstration and isolation

The `complete` cases in
[the operational Compose suite](../../tests/stewardship/test_operational_compose.py)
start a new disposable database and private native volume with no installed
ParishSoft or Workspace credential. They run the actual bootstrap, migration,
runtime-grant, web, scheduler, worker, mail and target-installer commands.
Both development and production profiles use the built application image.

One original authenticated browser submits the public wizard, sealed credentials,
normalized logo, source-load command, financial campaign, share options, content,
schedules, readiness test and final confirmation. Its requests pass through the
actual Django middleware and restricted web SQL identity. Only Google exchange/
certificate retrieval is synthetic; state, PKCE, nonce, JWT validation, CSRF,
session policy and current authorization remain real.

The source and delivery owners retain real journals, restricted SQL identities,
handoff encryption, private mounts, fences and immutable completion evidence.
Only the external provider responses are replaced. No real parish data or
provider credentials are used, and no real email is sent. Finite helper-process
and uncertain-delivery behavior have separate unit/PostgreSQL acceptance cases;
the Compose stub is not evidence of real provider connectivity.

The host recreates each required consumer from a complete configured topology
and invokes acknowledgement inside that actual running service, never an
ephemeral replacement process. The web never receives Docker access or a target
installer's private filesystem. Completion returns the original browser to the
ordinary Admin portal in Testing with a draft campaign. Read-only operator SQL
then verifies financial-source counts, eligible Family codes, coherent population,
terminal staging scrubbing and absence of live mail fulfillment.

The production-profile form driver uses Django's test client inside the real
web service. It is not a replacement for the separate real Caddy TLS/ingress
checks or the three-engine browser suite.

## Acceptance map

| Required relationship | Executable evidence |
| --- | --- |
| Empty deployment through configured Testing campaign | Both `complete` Compose cases, plus restricted finalization producer/consumer tests |
| Exact YAML/database agreement and interrupted installation | Setup YAML preparation, configuration cancellation, startup and completion PostgreSQL suites |
| Aborted or expired staging cannot return | Setup expiry, credential installation, staged/final disposal and stale-worker tests |
| Full/delta promotion is atomic and failures preserve truth | Source execution, delta, rejection, failure, fallback and outcome PostgreSQL suites |
| Family identities survive inactive/reactivated source rows | Source Family reconciliation and credential lifecycle/race suites |
| Ministry inactivity survives import and preserves manual roles | Ministry activity, chair reconciliation, seed evidence and source-effects suites |
| Page/email previews do not create live fulfillment | Setup/content preview, campaign readiness-mail and browser suites; final Compose SQL proof |

The tests live under [database](../../tests/stewardship/database),
[browser](../../tests/stewardship/browser) and
[stewardship](../../tests/stewardship). Each test's assertions, rather than its
filename alone, define the proof. See the
[database guide](stewardship-database-tests.md) for the fixed disposable services.

## Integrated validation status

- Latest baseline during round-2 corrections: 4,210 passed; 2,581 explicit profile
  skips; two existing warnings in 33.15 seconds. These skips require their
  separate opt-in suites below.
- Browser: 447 passed across the supported engines, with no skipped cases.
- Operational Compose: all six cases passed in 489.90 seconds, including both
  complete initial-setup profiles with a saved invitation schedule and no live
  occurrences or fulfillment. The earlier complete pair passed in 257.30 seconds.
- Full PostgreSQL coverage: the latest complete diagnostic run finished with
  2,066 passes and one dashboard query-budget failure. Its 90% combined coverage
  is not an acceptance pass. The focused performance rerun passes after removing
  redundant transaction overhead; the 64-query budget is unchanged. A new full
  run must validate all [round-2 corrections](stewardship-phase-2-full-review-2.md).
- Ruff and formatting pass; Markdown checks include this acceptance index.
  Final checks must repeat against the reviewed commit.
- Three independent full-phase dual-model review/fix rounds: not complete.
  Both models completed rounds 1 and 2 without degradation: respectively 36
  and 23 validated Medium findings, no High/Critical. Round-2 corrections and
  regression checks are in progress; round 3 has not started.

No Phase 2 PR or phase-exit approval is implied by these partial validation
results. Do not begin the Family implementation phase or merge this branch here.

## Boundaries retained for later phases

Phase 2 enables source refresh, initial setup and preparation, not live campaign
operation. Production transitions, Family submission/merge, scheduled live mail,
ministry follow-up, census publication, reports, restore release and exceptional
purge retain their controlling-plan owners. Mixed-phase DAT-04/DAT-05 tasks keep
their remaining submission/mail/seed-confirmation work explicitly separate from
the source-population and chair-suggestion integration delivered here.
