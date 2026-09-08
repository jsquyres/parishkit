# Stewardship milestones and review tasks

[Task index](README.md) · [Task execution plan](overall.md) ·
[Controlling plan](../../plans/stewardship/overall.md)

Implementation completion lives in the eight subsystem task lists. This file
tracks integration evidence and gate completion, not a second copy of package
status. Execute each phase's exact package order and partial-package scope from
the controlling plan. A review gate remains open until its whole protocol and
exit criteria pass, even if all implementation checkboxes are checked.

## Phase 0: Skeleton

Scope: [Phase 0](../../plans/stewardship/overall.md#phase-0-reproducible-project-skeleton).

- [x] M0.01 — Demonstrate local bind-mount reload, routes, and internal health.
- [x] M0.02 — Run the same baseline tests on the host and in the image.
- [x] M0.03 — Demonstrate safe startup rejection for incomplete production settings.
- [ ] M0.04 — Review and correct the scaffold before foundation work.

Evidence: September 7, 2026, macOS/arm64 host and Linux/arm64 image. The
[OPS-01 evidence](operations.md#ops-01-development-and-production-compose-topology)
records 570 passing baseline tests on both environments and 5 passing opt-in
Compose checks. Production rejects startup rather than using development keys.
OPS-09 coverage/CI and DOM-05 clock/traceability now implement their Phase 0
scope. Final pre-review validation passed 614 tests on both host and rebuilt
image (3 opt-in checks skipped), and all 5 separately enabled Compose tests.
Host scoped coverage is 96.99% lines and 95.29% branches at that pre-review SHA.
M0.04 is in progress; no foundation work or formal gate is released.

First M0 review: September 7, 2026, reviewed implementation SHA `b5bdc01`, base
`c810839`, local session `20260907-194036-a3712e`. Codex and three Claude shards
completed with no reviewer failures after the authorized findings-validation
retry. The finalized verdict was COMMENT: 12 validated Medium findings (10
Claude-only, 2 Codex-only), no agreed findings. This is not gate approval.

Initial triage (Claude findings C1–C10 and Codex findings X1–X2 in finalized
order):

- Auto-fixed C1: updated task evidence to the rebased implementation commits.
- Auto-skipped C2 as a duplicate of C1; campaign-domain evidence is corrected.
- Auto-fixed C5 and C7: logging tests now install sentinel handlers, verify
  closure/routing, and capture actual redacted stderr JSONL from root and all
  five framework/service logger routes. This tests the configuration hook,
  not future Gunicorn/Celery startup integration.
- Auto-fixed C6: wrapper documentation lists all commands and filesystem effects.
- Auto-skipped C8 as already handled by the explicit OPS-02 path-integration
  deferral in the [Compose guide](../../development/stewardship-compose.md#configuration-and-unfinished-boundaries).
  Typed deployment paths are not yet connected to a running consumer.
- Auto-skipped C9 as a false-positive: the clock helper deliberately exposes
  standard ZoneInfo errors, has no request caller, and promises no single error
  type. Request-boundary validation must accompany its future HTTP consumers.
- Auto-skipped C10 as already assigned to OPS-02/ARC-06 ownership and mount
  integration in the [authority guide](../../development/stewardship-authority.md).
  Cross-UID authority readability remains an integration requirement; the
  scaffold neither mounts these files to web nor enables production consumers.
- Fixed C3 with human approval: shared parser selection preserves existing
  tools' full option set; stewardship exposes config-only shared flags and the
  coverage runner exposes none. Command-inapplicable flags fail before dispatch,
  `--version` is standalone, and long-option abbreviations are disabled for
  stewardship. Regression tests cover real no-write rejection, all unsupported
  shared flags, all inapplicable command/option pairs before and after the
  command, redacted option diagnostics, help, and coverage-runner nonexecution.
- Fixed C4 with human approval: deployment parsing recognizes every existing
  ParishKit top-level section without interpreting other tools' fields. Unknown
  sections (including `deploymnet`) still fail. Regression tests load all eight
  tool examples with and without explicit deployment metadata, verify section
  isolation, and reject unknown names even alongside a valid deployment section.
- Fixed X1 with human approval: strict reads now bound bytes actually read,
  composition nodes/depth, and alias-expanded nodes/depth before construction
  or merge flattening. Unexpected recursion and invalid UTF-8 become sanitized
  ConfigError responses. Existing authority checks and legacy non-strict loading
  remain intact. Tests cover inclusive limits, bounded reads despite file growth,
  cycles, deep mappings/alias chains, merge amplification, ordinary alias/merge
  compatibility, and redacted deployment/CLI/authority read failures. The earlier
  isolated diagnostic reproduced the original uncaught 550-level recursion.
- Fixed X2 with human approval: host/CI installs preinstall the build lock and
  disable isolated editable-build dependency resolution. Release packaging uses
  the installed locked build tools too; no release was run. Checkout instructions
  match this order, and eight regression tests cover workflow commands, build-lock
  compatibility, Docker parity, and documentation. The test-only Compose service
  mounts the required workflow/documentation fixtures read-only.

All 12 validated findings have triage dispositions: 4 auto-fixed, 4 auto-skipped,
4 fixed with human approval, and no interactive skips or remaining decisions.
This closes the first triage pass, not M0.04 or the required re-review.

Initial corrections passed 619 host tests (3 opt-in Docker checks skipped),
Ruff checks/formatting, and tracked Markdown lint. After C3, the complete host
coverage runner passed 680 tests (3 opt-in Docker checks skipped), with 97.04%
scoped lines and 95.49% scoped branches. After C4, 703 host tests passed (3 opt-in
Docker checks skipped), with the same scoped coverage. After X1, 728 host tests
passed (3 opt-in Docker checks skipped), with 97.13% scoped lines and 95.70%
scoped branches. After X2, a fresh Python 3.12.13 environment installed both locks
successfully; `pip check` passed and all 78 applicable installed distributions
matched their lock entries. Its complete host suite passed 736 tests (3 opt-in
Docker checks skipped), with 97.13% scoped lines and 95.70% scoped branches.
Ruff checks/formatting, tracked Markdown lint, and migration drift checks passed.
The development image was rebuilt, and all 5 opt-in Compose checks passed,
including the complete in-image baseline, reload, private routes, durable
replacement, and production refusal. Corrections are committed for re-review:
pika branch mode compares committed HEAD, so the dirty-tree attempt in session
`20260907-202524-ac35dc` was aborted before Claude launch and has no verdict.
Re-review and human gate approval remain pending.

## Phase 1: Secure foundation

Scope: [Phase 1](../../plans/stewardship/overall.md#phase-1-secure-foundation-and-durable-domain).

- [ ] M1.01 — Demonstrate fake-provider Google login, denial, and session expiry.
- [ ] M1.02 — Demonstrate Family access and exact campaign-boundary denial.
- [ ] M1.03 — Prove single-current-campaign constraints under concurrent requests.
- [ ] M1.04 — Verify service mounts, configuration activation, and restart durability.
- [ ] M1.05 — Complete Gate 1 before beginning Phase 2.

Evidence: Not started.

## Gate 1: Foundation and security

Scope: [Gate 1](../../plans/stewardship/overall.md#review-gate-1-foundation-and-security).
Apply the complete [review protocol](../../plans/stewardship/overall.md#review-gate-protocol).

- [ ] G1.01 — Prepare coherent signed commits and pass gate-specific validation.
- [ ] G1.02 — Obtain two independent reviews of the complete gate diff.
- [ ] G1.03 — Triage findings, implement corrections, and add regression coverage.
- [ ] G1.04 — Repeat validation, the phase demonstration, and independent review.
- [ ] G1.05 — Resolve all validated Critical/High/Medium findings; document Low deferrals.
- [ ] G1.06 — Record reviewed SHA, evidence, and human approval before phase release.

Evidence: Not started.

## Phase 2: Setup and source truth

Scope: [Phase 2](../../plans/stewardship/overall.md#phase-2-source-truth-initial-setup-and-campaign-preparation).

- [ ] M2.01 — Demonstrate empty deployment through a configured Testing campaign.
- [ ] M2.02 — Prove YAML/database agreement and safe installer/wizard interruption.
- [ ] M2.03 — Demonstrate atomic full/delta refresh and stable campaign identities.
- [ ] M2.04 — Preview each Family page/email without creating live fulfillment.
- [ ] M2.05 — Complete the focused import/setup correction pass before the Family slice.

Evidence: Not started.

## Phase 3: Family response

Scope: [Phase 3](../../plans/stewardship/overall.md#phase-3-complete-family-response-vertical-slice).

- [ ] M3.01 — Demonstrate the minimal login-to-submit-to-repeat-visit vertical slice.
- [ ] M3.02 — Exercise every enabled-module combination and all Family response fields.
- [ ] M3.03 — Prove in-memory drafts, atomic submission, and stale/duplicate protection.
- [ ] M3.04 — Demonstrate upstream merge, proposal provenance, and follow-up supersession.
- [ ] M3.05 — Complete representative mobile/accessibility/privacy evidence and Gate 2.

Evidence: Not started.

## Gate 2: Data, privacy, and Family UX

Scope: [Phase 3 and Gate 2](../../plans/stewardship/overall.md#phase-3-complete-family-response-vertical-slice).
Apply the complete [review protocol](../../plans/stewardship/overall.md#review-gate-protocol).

- [ ] G2.01 — Prepare coherent signed commits and pass gate-specific validation.
- [ ] G2.02 — Obtain two independent reviews of the complete gate diff.
- [ ] G2.03 — Triage findings, implement corrections, and add regression coverage.
- [ ] G2.04 — Repeat validation, the phase demonstration, and independent review.
- [ ] G2.05 — Resolve all validated Critical/High/Medium findings; document Low deferrals.
- [ ] G2.06 — Record reviewed SHA, evidence, and human approval before phase release.

Evidence: Not started.

## Phase 4: Production scheduling and mail

Scope: [Phase 4](../../plans/stewardship/overall.md#phase-4-production-scheduling-delivery-and-notifications).

- [ ] M4.01 — Demonstrate Testing routing and operational-alert classification.
- [ ] M4.02 — Prove resumable Testing cleanup and atomic Production activation.
- [ ] M4.03 — Exercise scheduled mail, receipts, and digests through outages and retries.
- [ ] M4.04 — Verify unknown delivery, pause/resume, and close-during-pause behavior.
- [ ] M4.05 — Recheck real service queue/mount needs using fake-backed integrations.

Keep live dispatch and final Production activation within the environments
permitted by the master plan until Gate 3 is complete.

Evidence: Not started.

## Phase 5: Reporting and staff workflows

Scope: [Phase 5](../../plans/stewardship/overall.md#phase-5-reports-exports-users-and-follow-up).

- [ ] M5.01 — Demonstrate all report formats and historical campaign selection.
- [ ] M5.02 — Verify Family-code, financial, and assigned-Ministry access boundaries.
- [ ] M5.03 — Prove shared values across web, charts, exports, and pinned digests.
- [ ] M5.04 — Deny queued/download access after role or assignment revocation.
- [ ] M5.05 — Complete Gate 3 before beginning publication and destructive workflows.

Evidence: Not started.

## Gate 3: Async processing, RBAC, and reports

Scope: [Gate 3](../../plans/stewardship/overall.md#review-gate-3-async-processing-rbac-and-reporting).
Apply the complete [review protocol](../../plans/stewardship/overall.md#review-gate-protocol).

- [ ] G3.01 — Prepare coherent signed commits and pass gate-specific validation.
- [ ] G3.02 — Obtain two independent reviews of the complete gate diff.
- [ ] G3.03 — Triage findings, implement corrections, and add regression coverage.
- [ ] G3.04 — Repeat validation, the phase demonstration, and independent review.
- [ ] G3.05 — Resolve all validated Critical/High/Medium findings; document Low deferrals.
- [ ] G3.06 — Record reviewed SHA, evidence, and human approval before phase release.

Evidence: Not started.

## Phase 6: Reconciliation and campaign completion

Scope: [Phase 6](../../plans/stewardship/overall.md#phase-6-reconciliation-and-post-campaign-operations).

- [ ] M6.01 — Demonstrate proposal review, conflicts, manual outcomes, and partial publication.
- [ ] M6.02 — Prove source fencing, verification, and safe retry of unresolved entities.
- [ ] M6.03 — Restore an isolated backup and exercise every release/pointer state.
- [ ] M6.04 — Demonstrate reopen, post-close mail resolution, archive, and Return to Testing.
- [ ] M6.05 — Exercise purge gates, rollback limits, resume, cleanup, and tombstones on disposable data.
- [ ] M6.06 — Complete Gate 4 before release hardening can declare these workflows ready.

Evidence: Not started.

## Gate 4: External writes and destructive workflows

Scope: [Gate 4](../../plans/stewardship/overall.md#review-gate-4-external-writes-and-destructive-workflows).
Apply the complete [review protocol](../../plans/stewardship/overall.md#review-gate-protocol).

- [ ] G4.01 — Prepare coherent signed commits and pass gate-specific validation.
- [ ] G4.02 — Obtain independent transaction/migration and security/authorization reviews.
- [ ] G4.03 — Run authorized isolated restore/purge exercises and boundary failure injection.
- [ ] G4.04 — Triage findings, implement corrections, and add regression coverage.
- [ ] G4.05 — Repeat validation, demonstrations, and independent review after corrections.
- [ ] G4.06 — Resolve every validated Critical/High/Medium finding; document Low deferrals.
- [ ] G4.07 — Record reviewed SHA, evidence, and human approval before phase release.

Evidence: Not started.

## Phase 7: Release readiness

Scope: [Phase 7](../../plans/stewardship/overall.md#phase-7-production-hardening-and-release-readiness).

- [ ] M7.01 — Close every subsystem task and acceptance traceability entry.
- [ ] M7.02 — Complete supported-browser, scale, coverage, and accessibility verification.
- [ ] M7.03 — Validate production images and exercise the documented operational runbooks.
- [ ] M7.04 — Collect authorized human-run integration smoke-test evidence.
- [ ] M7.05 — Complete retention/privacy review and operator/developer handoff documents.
- [ ] M7.06 — Demonstrate the full disposable campaign lifecycle from production images.
- [ ] M7.07 — Complete Gate 5 before release artifact publication.

Evidence: Not started.

## Gate 5: Release readiness

Scope: [Gate 5](../../plans/stewardship/overall.md#review-gate-5-release-readiness).
Apply the complete [review protocol](../../plans/stewardship/overall.md#review-gate-protocol).

- [ ] G5.01 — Prepare the complete review diff and pass all required release validation.
- [ ] G5.02 — Obtain two independent reviews of the complete implementation.
- [ ] G5.03 — Triage findings, implement corrections, and add regression coverage.
- [ ] G5.04 — Repeat full validation and independent review of the corrected diff.
- [ ] G5.05 — Resolve release blockers and record all permitted Low deferrals.
- [ ] G5.06 — Record reviewed SHA and human product/security/operations approval.
- [ ] G5.07 — Complete the normal PR handoff and separately authorized release procedure.

Evidence: Not started.
