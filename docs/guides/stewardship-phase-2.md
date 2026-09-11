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

DAT-03 is in progress. The first internal checkpoint implements normalized
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

The complete source/setup/configuration batch will receive at least three
independent review/fix rounds and passing local/PR CI before human merge
approval. Normal validation uses synthetic data and fake providers. Later
Family response, production delivery, publication, backup/restore and destructive
workflows retain their controlling-plan owners.
