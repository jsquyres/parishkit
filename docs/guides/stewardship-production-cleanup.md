# Production-transition cleanup implementation checkpoint

[Tasks](../tasks/stewardship/background-processing.md#bg-03-production-transition-cleanup-worker) ·
[Work package](../plans/stewardship/background-processing.md#bg-03-production-transition-cleanup-worker) ·
[Cleanup contract](../specs/stewardship/background-processing/spec.md#production-transition-cleanup) ·
[Controlling delivery plan](../plans/stewardship/overall.md#automated-phase-delivery-cycle)

## Scope and starting point

Branch `pr/stewardship-production-cleanup` starts from verified PR #32 merge
`5c85d26ff586cad5539ff2c324c89cd621cbcf9d` on refreshed `origin/main`.

Deliver BG-03's five items as one independently testable general-worker
increment: exact Testing inventory and non-sensitive aggregate, atomic gate and
epoch invalidation, bounded checkpointed deletion, completion verification,
retry/recovery and safe cancellation. The existing Production journal is a
foundation, not evidence that these operational owners already exist.

Keep the later ADM-05 readiness/activation web workflow, BG-04 schedule owners
and BG-06 dispatch owners disabled. Cleanup never changes mode or lifecycle.
Normal validation uses synthetic data, disposable databases and fake providers;
no retained database deletion, real provider writes, deployment or release is
authorized by this increment. Gate 3 remains after complete Phase 4/5 integration.

## Validation checkpoints

- Exact inventory/category ownership and aggregate privacy, including mixed
  Testing/live/operational and other-campaign preservation.
- Bounded transactions, checkpoint/deletion atomicity, interruption/replay,
  superseded claims, cancellation and verified completion.
- Rehearsal invalidation and denial of concurrent Testing work; stable Production
  codes and anonymous rehearsal code reservations remain intact.
- Actual restricted runtime roles, SQL denial tests, worker configuration
  authority and fresh-install schema/catalog validation.
- Credential-free baseline, Ruff, formatting, Markdown and relevant Compose
  checks, followed by the required three dual-source review/fix rounds.
- Exact-head PR CI and all merge-group checks, then protected delivery and
  verification on refreshed `origin/main` before the next increment.

Implementation is in progress. No BG-03 task or review gate is claimed complete.

## Implemented working-tree checkpoint

The compiled general worker now captures a sealed, independently SQL-verified
17-category inventory, deletes dependency-ready bounded batches with atomic
checkpoints, and verifies completion against both retained membership and actual
Testing data. Private transaction proofs authorize only the inventoried deletes;
runtime roles cannot read private target membership or forge those proofs.
Terminal Testing mail detail is removed while Production/operational mail,
stable Production identities and anonymous rehearsal reservations are preserved.

Cancellation is a durable Admin intent honored at worker/recovery boundaries;
partial deletion is never rewound. Exhausted retries retain the gate and emit a
deduplicated non-sensitive critical event. Explicit retry creates a journaled
child task. Internal request ports remain unavailable as web activation/readiness
workflows until ADM-05 supplies its authoritative checks and UI.

Local synthetic-data validation before the first independent review:

- 61 cleanup tests passed in 65.65 seconds; scoped coverage is 91%.
- 5,554 credential-free baseline tests passed in 56.43 seconds; 3,553
  environment-gated tests skipped, with two existing warnings.
- 138 journal/schema/storage/schedule regressions passed in 69.68 seconds.
- An independent fresh-schema comparison against PR #32 passed before accepting
  the updated catalog fixture: four added tables, 29 columns, 44 constraints,
  21 functions, 12 indexes and 30 Stewardship triggers, with no removed objects.
  Changes to existing objects are limited to one event constraint and nine
  functions for deletion authorization and private control metadata. Django
  session deletion protection is checked separately. No retained database was
  upgraded or deleted.
- Django reports no missing migration state; this remains a fresh-install
  baseline, not an upgrade contract.

The first Claude permission probe appended a stray period to its validator
command and was denied. The exact-command retry passed with no permission
denials, byte-identical fixture delivery and parent validation. Neither probe
reviewed code or counts toward the three required rounds.

Independent review rounds, additional race/admission acceptance evidence,
operational validation and final-head/merge-group CI remain outstanding.
