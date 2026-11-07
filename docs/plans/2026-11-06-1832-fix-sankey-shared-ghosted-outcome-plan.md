---
title: Sankey Shared Ghosted Outcome - Plan
type: fix
date: 2026-11-06
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---
# Sankey Shared Ghosted Outcome - Plan

## Goal Capsule

- **Objective:** Report readers can compare application outcomes in one final column without fragmented silence endpoints.
- **Means:** Reuse position-aware endpoint aggregation (KTD1).
- **Authority:** Product requirements govern behavior; technical decisions govern implementation within those requirements.
- **Execution:** Small local reporting change, implemented and verified inline; LFG owns review, commits, PR, and CI. Merge remains with the user.
- **Stop conditions:** A conflict with the agreed behavior or an unverified prerequisite that prevents safe implementation.

## Product Contract

### Summary

Combine silence endpoints into Ghosted and align Accepted with the other final outcomes. Use a two-week interview waiting threshold.

### Problem Frame

Splitting silence across multiple endpoints makes outcomes harder to compare, and Accepted currently appears among intermediate stages.

### Requirements

- R1. All terminal recorded ghosted paths and inferred interview-waiting paths converge on a single node labeled `Ghosted`, combining counts and contributor IDs.
- R2. Infer interview silence at a known current-stage age of at least 14 days, retaining existing same-round and new-round timing semantics.
- R3. Terminal `accepted`, `rejected`, `withdrawn`, and Ghosted endpoints share the rightmost column, including paths ending after different interview rounds.
- R4. Preserve recorded statuses, history, current-status evidence, and the distinction between inferred and recorded transition evidence.
- R5. Explain the 14-day inference in report caveats and evidence tables; preserve accurate counts, forward-only paths, and reopened-outcome behavior.

### Key Decisions

- **Combine silence for chart readability.** Governs R1, R4. (session-settled: user-approved — chosen over separate recorded/inferred endpoints: the user accepted aggregation after the report-only inference distinction was explained.)
- **Use two weeks of interview silence.** Governs R2, R5. (session-settled: user-directed — chosen over 30 days: the user explicitly requested the shorter threshold.)

### Scope Boundaries

Change web reporting only. Leave tracker status transitions, database data, legacy TUI Sankey, and unrelated aging/inventory thresholds as they are.

### Acceptance Examples

- AE1. Covers R1, R4: a recorded pre-interview ghosted application and an interview application waiting 14 days share one endpoint; their evidence rows still identify recorded versus inferred transitions.
- AE2. Covers R2: an interview stage aged just under 14 days gets no inference; exactly 14 days does. Unknown age gets no inference.
- AE3. Covers R3, R5: acceptance after a short path shares the final column with rejection after a longer path; reopened acceptance remains an intermediate historical step when followed by another event.

## Planning Contract

### Key Technical Decisions

- KTD1. **Separate chart labels from evidence identities.** In `cv_optimizer/reporting/sankey_report.py`, map both silence types to the same chart node key while retaining distinct raw transition groups and current-status labels (R1, R4). Aggregate derived-node metadata from raw statuses rather than the now-shared label. Existing link flags retain their inference provenance.
- KTD2. **Extend the existing terminal-status set.** Add accepted to the set that already handles rejected/withdrawn endpoints and reopened outcomes (R3). The SVG renderer already positions nodes by report positions.
- KTD3. **Keep the inference threshold and its explanation consistent.** Update the report condition and caveat together with `static/reports.js` evidence-basis text (R2, R5); no library change is needed.

### Grounding

`sankey_report` already aggregates by position/label and distinguishes inference through `MID_INTERVIEW_WAITING`. `tests/test_reporting_interview_waiting.py` covers timing and nonmutation, while `tests/test_reporting_presentation.py` samples SVG paths to detect overlaps. Local patterns suffice; external research adds no value for this business-logic change.

## Implementation Units

### U1. Unify final outcomes and shorten interview inference

- **Goal:** Deliver R1–R5 in the report model and evidence copy.
- **Dependencies:** None.
- **Files:** `cv_optimizer/reporting/sankey_report.py`, `static/reports.js`, `tests/test_reporting_sankey.py`, `tests/test_reporting_interview_waiting.py`, `tests/test_reporting_presentation.py`.
- **Approach:** Apply KTD1–KTD3 using existing aggregation and rendering conventions. Keep mixed recorded/inferred contributors traceable through links and evidence groups.
- **Test scenarios:**
  1. Covers AE1: merge pre-interview, post-engagement, and inferred silence while preserving contributor counts and evidence basis.
  2. Covers AE2: exercise just-under/exactly/over 14 days, unknown stage age, repeated same-round events, and new-round reset.
  3. Covers AE3: merge accepted outcomes across short and long paths and retain reopened acceptance without backward links.
  4. Render shared Ghosted and Accepted endpoints, assert final-column alignment and inward captions, and retain flow overlap checks.
  5. Verify the presentation identifies inferred transitions with the 14-day explanation.
- **Verification:** Targeted reporting tests pass, report input facts are not mutated, and browser evidence shows the desired final column.

## Verification Contract

- Run `python3 -m pytest tests/test_reporting_sankey.py tests/test_reporting_interview_waiting.py tests/test_reporting_presentation.py` for changed behavior.
- Run `python3 -m pytest tests/test_reporting_*.py` for report regressions.
- Inspect `http://localhost:8000/reports` in a real browser, including the overview and full Sankey, with console-error checks. Use synthetic report data if live data has no accepted outcome.
- Check the final diff for unrelated changes and stale 30-day interview inference text.

## Definition of Done

U1 satisfies R1–R5 and the verification contract. The diff contains no experimental code or unrelated cleanup. Review findings are resolved or recorded, and the change is committed and shipped through LFG's PR workflow.
