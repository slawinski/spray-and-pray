---
title: Advisory Content Validation - Plan
type: fix
date: 2026-10-19
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---
# Advisory Content Validation - Plan

## Goal Capsule

- Objective: Users receive generated CVs and cover letters even when content checking finds concerns or cannot complete, with visible warnings explaining their advisory status.
- Means: Advisory checker results and best-effort warning transport (KTD1–KTD3).
- Authority: Product requirements below govern behavior; implementation units preserve existing publication integrity.
- Execution: Autonomous implementation, verification, review, and open PR; merging remains with the user.
- Stop conditions: Invalidated settled decisions or an unavailable required repository prerequisite.

## Product Contract

### Summary

Remove literal skill bans and turn the new document content gate into advisory checking.
Publish generated documents despite content findings or checker failures, and show warnings locally and in completion flows.

### Problem Frame

The dual-profile checker blocks legitimate mechanical and IT generation.
Literal skill matching rejects historical tool references, while semantic rejection details can be truncated in the TUI and have no durable local log copy.

### Key Decisions

- Remove literal skill bans (session-settled: user-directed — chosen over a narrow deterministic skill backstop: matching blocks legitimate CV generation). Governs R1.
- Warn and publish (session-settled: user-directed — chosen over a semantic publication gate or disabling checking: retain useful advice without blocking documents). Governs R2, R3.

### Requirements

**Content policy**
- R1. Remove literal excluded-skill checks entirely, including historical references and Skills sections.
- R2. Literal excluded employment titles/identities and negative semantic verdicts produce warnings rather than aborting publication.
- R3. Checker construction, provider errors, unavailable or malformed verdicts, and other content-check failures produce warnings rather than aborting publication; never describe an incomplete check as passed.

**Visibility and integrity**
- R4. Log full advisory reasons locally and surface safe summaries in TUI and initial/later server completion notifications, without exposing quoted rejected document text externally.
- R5. Warning delivery failures cannot prevent publication or turn published documents into a reported generation failure.
- R6. Keep profile selection, valid source projection, writer/renderer failures, and transactional profile-revision publication guards effective.
- R7. Preserve the single independent checker call, without a rewrite loop, new provider, or application-level retry.

### Scope Boundaries

No persistence migration or warning history UI is needed: local logs retain details and current-run completion flows receive summaries.
No automatic rewriting or retries are planned (R7).
Personal career facts and pre-existing configuration edits must not enter commits.

## Planning Contract

### Key Technical Decisions

- KTD1. Return a small advisory result from `DocumentValidator.validate`, carrying local detail and safe summary information. A positive semantic result cannot erase literal employment findings (R2, R3).
- KTD2. Keep the advisory boundary in `tracker._generate_document`, including checker construction failures. Perform publication through the existing `publish_document` transaction; send best-effort warning callbacks only after successful publication (R3, R5, R6).
- KTD3. Add optional keyword-only warning callbacks to tracker entrypoints while retaining existing ID/path return values. TUI and server aggregate safe summaries into completion messages; local logs retain full quotes and reasons (R4).

### High-Level Technical Design

The writer supplies cleaned Markdown to the advisory checker, whose result feeds local logging.
The tracker passes the same Markdown to transactional publication.
After successful publication, the tracker invokes an optional warning callback; TUI/server completion messages use only its safe summary.
Selection, source, writer, renderer, and publication exceptions stay outside the advisory catch boundary.

### Assumptions

The existing logging setup is the local detail destination; warning status need not survive a new process.
The server's initial and later-letter wrappers and TUI worker completions are the affected user-facing surfaces; no browser-rendered page changes.

## Implementation Units

### U1. Advisory checker results

**Goal:** Implement R1–R3 and R7.
**Dependencies:** None.
**Files:** `cv_optimizer/document_validation.py`, `cv_optimizer/prompts/validate_document.md`, `tests/test_document_validation.py`.
**Approach:** Follow the existing strict verdict parser and independent checker payload; retain employment matching, remove skill matching, and accumulate findings with a safe status summary (KTD1).
**Test scenarios:**
- Excluded skill names alone yield no literal warning with a positive checker verdict.
- Excluded employment title or identity yields advisory detail even with a positive verdict.
- Negative verdict retains quote and correction reason; malformed responses and provider failures report incomplete checking.
- Invalid profile context remains rejected; no automatic retries occur.
**Verification:** Checker boundary tests demonstrate distinct pass, findings, and unavailable states.

### U2. Publish and report advisory status

**Goal:** Implement R3–R6.
**Dependencies:** U1.
**Files:** `cv_optimizer/tracker.py`, `cv_optimizer/tui/app.py`, `server.py`, `tests/test_profile_generation.py`, `tests/test_tui_profiles.py`, `tests/test_profile_requests.py`.
**Approach:** Apply KTD2–KTD3 using current entrypoints and publication seams. Keep local details out of callbacks and external failure messages. Aggregate warnings into successful completion messages rather than presenting approval.
**Test scenarios:**
- Initial CV and letter, replacement CV, and later letter publish despite negative, malformed, unavailable, and constructor-failing checks.
- A warning callback that raises cannot prevent or undo publication.
- Server ready messages include advisory status without synthetic secret excerpts; notification failures do not produce false generation-failure messages.
- TUI pilot exercises warning-bearing CV and letter completions.
- Existing unselected profile, invalid source, stale revision/ABA, writer/renderer, and publication rollback protections remain green.
**Verification:** Integration tests use synthetic sources, fake checker completions, and real publication/database seams.

### U3. Explain the advisory policy

**Goal:** Document R1–R7.
**Dependencies:** U1, U2.
**Files:** `README.md`.
**Approach:** Replace strict-gate language with advisory policy, warning destinations, and retained integrity guards.
**Test expectation:** None — documentation only; verify wording against implemented behavior.

## Verification Contract

Run `python3 -m pytest tests/test_document_validation.py tests/test_profile_generation.py tests/test_profile_requests.py tests/test_tui_profiles.py -q`, then `python3 -m pytest tests/ -q`.
Use Textual's existing automated pilot for changed TUI flows; no browser route renders this change.
Run `git diff --check`, simplify the scoped diff, and review against R1–R7 before shipping.
No paid model call is required or claimed.

## Definition of Done

All units are implemented and verified, advisory warnings reach the affected completion flows, and integrity regressions remain protected.
No abandoned implementation or sensitive data is committed.
Commit intended files, push a follow-up branch from merged main, create an open PR, and report CI honestly without treating absent checks as passing.
