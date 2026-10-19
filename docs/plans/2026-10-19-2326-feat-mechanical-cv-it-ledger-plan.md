---
title: Mechanical CV IT Ledger - Plan
type: feat
date: 2026-10-19
topic: mechanical-cv-it-ledger
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Mechanical CV IT Ledger - Plan

## Goal Capsule

- **Objective:** Reduce the space occupied by IT employment in the Mechanical Engineering CV so the candidate's engineering experience is easier to reach.
- **Means:** A compact IT work-history ledger without achievement prose.
- **Product authority:** The user-confirmed Product Contract below defines scope and behavior.
- **Open blockers:** None; generation and rendering direction is defined in the Planning Contract.
- **Execution:** Implement and verify locally; authorized LFG pipeline owns review and shipping to an open PR, without merge.

## Product Contract

### Summary

Present IT employment as compact title/company/date entries in the Mechanical Engineering CV.
Retain detailed engineering experience and preserve the separate IT CV presentation.

### Problem Frame

Repeated full-size IT role headings and achievement lists delay access to the candidate's historical engineering work, even when each IT role is marked brief.

### Key Decisions

- **Compact identities rather than full-size IT role blocks.** Governs R1, R3. (session-settled: user-directed — chosen over the other compression options in the ideation comparison: reduce repeated role scaffolding while retaining the employment record.)
- **Zero IT achievements.** Governs R2. (session-settled: user-directed — chosen over a shared allowance of one or two achievements: the candidate wants only IT employment identities in this CV.)
- **Keep chronological presentation.** Governs R4. (session-settled: user-approved — chosen over moving engineering ahead of recent IT employment: the confirmed scope retains the existing order.)

### Requirements

**IT work-history presentation**

- R1. The Mechanical Engineering CV must retain every IT role selected for that profile, including all seven currently selected roles, with its accurate historical title, company and employment dates.
- R2. Those IT entries must contain no achievement bullets or descriptive paragraphs.
- R3. Render the IT entries as a compact work-history ledger rather than separate full-size job sections, while keeping the text readable and allowing long identities to wrap.
- R4. Preserve reverse chronology across the selected employment history; compression must not merge distinct employments or alter their titles or dates.

**Profile isolation and engineering detail**

- R5. Retain detailed presentation of engineering roles using their approved source facts.
- R6. Leave the IT profile's source selections, detail rules and CV presentation unchanged.
- R7. Apply the compact presentation to newly generated or regenerated Mechanical Engineering CVs without rewriting saved documents merely because the feature is introduced.

### Key Flows

- F1. Generate or regenerate a Mechanical Engineering CV.
  - **Steps:** Use the selected profile's approved employment facts; present IT entries per R1–R4 and engineering roles per R5.
  - **Outcome:** The new CV has a compact IT history while preserving profile isolation under R6 and saved-document behavior under R7.

### Acceptance Examples

- AE1. **Covers R1–R5.** Given seven selected IT roles followed by older engineering roles, the rendered Mechanical Engineering CV includes all seven IT identities without achievement prose and gives engineering roles their detailed treatment in chronological order.
- AE2. **Covers R1, R3–R4.** Given an IT entry with a long title or company name, its compact entry wraps legibly without dropping identity fields or combining it with another employment.
- AE3. **Covers R5–R6.** Given the same career source, generating an IT CV keeps its existing IT detail rules; the ledger treatment applies only to the Mechanical Engineering CV.
- AE4. **Covers R7.** Given an existing saved Mechanical Engineering CV, introducing this feature leaves it untouched; regeneration produces the new presentation.

### Scope Boundaries

- No engineering-first section reordering, selective omission of IT roles, or new page-count guarantee.
- No change to cover-letter behavior, education, profile selection or publication revision guards.
- No new blocking content checks, automatic rewriting loop or broad CV redesign.
- The shared career record remains factual; this work changes CV presentation rather than deleting IT achievements from the master.

### Sources

- [Mechanical CV IT compression ideation](../ideation/2026-10-19-mechanical-cv-it-compression-ideation.html), C16: compact ledger with a shared achievement budget; the confirmed zero-achievement choice replaces that budget.
- [Dual CV profiles plan](2026-10-19-1239-feat-dual-cv-profiles-plan.md): background for profile-specific presentation and accurate employment history.

---

## Planning Contract

Product Contract unchanged; the former deferred planning items are resolved below.

### Key Technical Decisions

- KTD1. Add optional `cv_role_detail` overrides mapping selected mechanical-profile role IDs to `ledger`. Existing `roles` selectors remain the source policy for cover letters. CV resolution removes achievements from ledger roles and marks their effective detail as ledger. This instantiates R1–R3 without changing letters. (session-settled: user-directed — chosen over full-size IT role sections and an aggregate achievement allowance: retain identities with zero achievements.)
- KTD2. Use Markdown blockquote paragraphs for ledger identities within the single Experience section, interleaved with detailed role blocks in source order. Each paragraph carries exact title, employer, supplied location and dates; no extra Experience heading is introduced. Scoped blockquote CSS uses normal 10.5pt body text and compact margins, with natural line wrapping. This avoids the existing canonical-section overwrite behavior in `PDFGenerator`.
- KTD3. Resolve document type at the tracker boundary and use the same context for writer and advisory checker. The default resolver view is CV; cover-letter callers explicitly request the unchanged letter view. Legacy policies without overrides resolve identically.
- KTD4. Preserve the existing trust boundary: source projection prevents supplying ledger achievements to the CV writer; prompt and advisory checker specify output behavior. Do not add blocking semantic validation, hard page limits, automatic rewrites, or a new model call.

### High-Level Technical Design

The data flow is: canonical facts + profile selectors → document-specific resolver → writer → advisory checker → existing revision-guarded publisher → PDF renderer.
Only the CV branch applies `cv_role_detail`; the cover-letter branch uses the original selections.
Inside Experience, consecutive ledger paragraphs share a compact blockquote, and detailed jobs retain the existing heading/company/bullet layout.

### Assumptions and Risks

- Source experience ordering is already truthful reverse chronology; preserve it rather than parse or rewrite date strings.
- Ledger classification is an explicit policy selection, never inferred from job titles or all brief roles.
- Real-model compliance remains advisory, as with existing title/attribution contracts. Synthetic writer and PDF tests prove plumbing and layout, not paid-model semantic accuracy.
- Exact height reduction and pagination are execution-time measurements, not guarantees.
- The personal ignored master may receive only the approved CV presentation metadata after role IDs are checked locally; compare IT and cover-letter contexts before/after and retain all factual source records.

---

## Implementation Units

### U1. Project CV-only ledger policy

**Goal:** Supply identity-only ledger roles to the mechanical CV without changing other document contexts.
**Requirements:** R1, R2, R4–R7; AE1, AE3, AE4.
**Dependencies:** None.
**Files:** `cv_optimizer/profiles.py`, `cv_optimizer/tracker.py`, `master_cv.example.json`, `tests/test_cv_profiles.py`, `tests/test_profile_generation.py`.
**Approach:** Extend strict policy validation for KTD1, then pass document type through tracker resolution per KTD3. Keep source identities and excluded-achievement attribution intact. Update the synthetic example with an explicit ledger override.
**Patterns:** Existing `_prepare` deep-copy/select boundary and tracker selection snapshot.
**Test scenarios:**
1. Covers AE1/AE3. Explicit ledger selection removes its CV achievements while detailed engineering remains intact; IT and letter contexts equal the pre-override contexts.
2. Legacy brief roles without overrides retain achievements and presentation.
3. Unknown/unselected ledger IDs, invalid override values and overrides on IT are configuration errors under the existing strict policy contract.
4. Covers F1/AE4. Track/regenerate mechanical CV and generate its letter with distinct appropriate contexts; metadata changes alone leave saved artifacts untouched.
**Verification:** Source is unchanged by resolution, writer and checker receive identical document-specific contexts, existing publication revision tests pass.

### U2. Write and render compact chronological identities

**Goal:** Reduce repeated IT scaffolding and remove IT achievement prose in the mechanical CV.
**Requirements:** R1–R6; AE1–AE3.
**Dependencies:** U1.
**Files:** `cv_optimizer/prompts/optimize.md`, `cv_optimizer/prompts/validate_document.md`, `cv_optimizer/generator.py`, `tests/test_profile_prompts.py`, `tests/test_cv_ledger.py`.
**Approach:** Specify KTD2's ledger paragraph grammar as the exception to full role blocks. Add scoped CSS without changing regular role typography. Update advisory instructions to recognize zero-achievement ledger entries.
**Test scenarios:**
1. Covers AE1. Render seven synthetic ledger identities and five detailed engineering roles; assert all identities/dates, no IT achievement sentinels, engineering achievements, and global ordering in extracted PDF text.
2. Covers AE2. Long title/employer identities wrap across lines and remain fully extractable at readable font sizes within main-column bounds.
3. Interleaved ledger/detailed jobs and English/Polish Experience headings survive the parser without section collisions.
4. Covers AE3. IT renders its original full role blocks and selected achievements; letter prompt payload is unchanged.
5. Compare the same fixture with baseline full-size brief blocks and new ledger rows; measure the distance to first engineering role across page boundaries and inspect actual rendered output.
**Verification:** Real PDF text/geometry assertions and visual inspection demonstrate reduced footprint, with no paid completions.

### U3. Document and prepare the approved local profile

**Goal:** Make the feature usable for both the example and the approved local mechanical profile.
**Requirements:** R6, R7 and scope boundaries.
**Dependencies:** U1, U2.
**Files:** `README.md`, ignored `master_cv.json` (local only), `tests/test_cv_ledger.py`.
**Approach:** Explain optional CV-only policy, explicit role IDs, unchanged letters, and regeneration semantics. Add overrides for exactly the seven approved local IT IDs, preserving all other master data. Keep previews and private text ignored.
**Test scenarios:**
1. Before/after local comparison establishes identical canonical facts, IT context and mechanical letter context; mechanical CV retains twelve identities, seven ledger entries with zero achievements, and five detailed engineering roles.
2. Full suite remains green and tracked diff contains no personal source facts or generated private documents.
**Verification:** Report safe counts and layout measurements only; commit the anonymized ideation provenance and enriched plan.

---

## Verification Contract

- Run focused profile, prompt, generation and real-PDF ledger tests, then `python3 -m pytest -q` for the full suite.
- Use synthetic deterministic Markdown to compare baseline/new PDF geometry. Record pages and flow distance rather than infer tailored-output page savings.
- Inspect rendered pages, including a long identity and transition to detailed engineering. Browser QA is PDF-scoped; no web interface changes are planned.
- No paid model calls, new content gates or CI configuration are required. Query GitHub checks after shipping and report absent CI honestly.

---

## Definition of Done

- U1–U3 satisfy their test scenarios and R1–R7 without changing settled decisions.
- Local master preparation is proven with privacy-safe comparisons and is excluded from commits.
- Full suite and measured PDF layout checks pass; abandoned experimental code is removed.
- Simplification and code review findings are resolved or recorded in the PR; the feature is pushed as a separate PR against current main, with CI state reported and no merge.
