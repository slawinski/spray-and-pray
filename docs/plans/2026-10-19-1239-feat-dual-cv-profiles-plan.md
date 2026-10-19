---
title: Dual CV Profiles - Plan
type: feat
date: 2026-10-19
topic: dual-cv-profiles
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Dual CV Profiles - Plan

## Goal Capsule

- **Objective:** The candidate can prepare distinct IT and mechanical-engineering applications that present the appropriate parts of the same career.
- **Means:** One complete factual master with two manually selected presentation profiles, implemented through KTD1–KTD3.
- **Product authority:** The confirmed Product Contract below governs behavior and scope.
- **Implementation authority:** The Planning Contract governs mechanisms within the Product Contract; units override neither.
- **Execution:** Local code changes and verification; committing, pushing, and opening a PR require separate authorization.
- **Stop conditions:** Stop document generation on missing selection, invalid source policy, or failed content checks, per KTD1–KTD5.
- **Open blockers:** No product decisions block implementation planning; the old CV has been supplied and extracted, and the candidate confirmed the Life Cycle Data Engineer end date as March 2019. Final extraction review remains before completing the import.

---

## Product Contract

### Summary

Provide IT and Mechanical Engineering profiles over one complete career record.
Filter source facts by the chosen profile before tailoring, and preserve that selection across each application's CV and cover-letter generation.
Recover the missing engineering history through a one-time, candidate-reviewed import.

### Problem Frame

The candidate is a mechanical engineer with engineering experience from before 2019 and a more recent IT career.
The current master contains IT experience and skills; an older CV contains the missing engineering history.
Engineering applications need to foreground that earlier work, while IT applications must exclude mechanical jobs and mechanical-only skills without losing the engineering degree.

### Key Decisions

- **A shared factual master with separate editorial profiles.** Governs R1–R3; avoids maintaining divergent biographies. (session-settled: user-approved — chosen over separately maintained CV histories: facts should be recorded once while emphasis differs.)
- **Hard exclusion of mechanical employment from IT.** Governs R4–R6; eligibility is distinct from relevance ranking. (session-settled: user-directed — chosen over brief mechanical title/date entries: the candidate wants those jobs to disappear entirely.)
- **Manual profile selection.** Governs R10–R12; the candidate controls the application narrative. (session-settled: user-directed — chosen over suggested or automatic selection: explicitly select the intended CV type.)
- **One-time content recovery.** Governs R13; a reusable importer is unnecessary for this need. (session-settled: user-directed — chosen over a reusable CV-import feature: importing the existing old CV once is sufficient.)
- **Preserve IT compatibility and restrict new engineering material.** Governs R2 and R12; existing applications should not acquire engineering content after master enrichment. (session-settled: user-approved — chosen over implicit cross-profile inclusion or retroactive profile changes: both defaults were explicitly confirmed.)
- **Profile-specific education.** Governs R6; retain the existing IT education while expanding the engineering version. (session-settled: user-directed — chosen over globally expanding or replacing education: the candidate explicitly wants IT left as is.)

### Requirements

**Shared facts and eligibility**

- R1. Maintain one authoritative career record containing both IT and verified mechanical-engineering history, with two named profiles: IT and Mechanical Engineering.
- R2. Roles, achievements, skills, and positioning content must have explicit profile eligibility; newly added engineering content is engineering-only unless the candidate approves sharing it.
- R3. Tailoring must receive only facts eligible for the selected profile, including profile-approved summary content rather than an unrestricted master narrative.

**IT output and spillover prevention**

- R4. The IT CV must omit all mechanical-engineering employment entries and their achievements, including employer/title/date-only entries.
- R5. The IT CV must exclude mechanical-only skills and highlight relevant IT experience and skills.
- R6. Keep IT education exactly as currently presented and use the old CV's expanded education only for Mechanical Engineering, including separate master's and bachelor's degrees with their dates, specializations, and theses.
- R7. Check generated CV and cover-letter content against the selected profile's exclusions before treating the documents as ready, and identify any violation for correction.

**Engineering presentation and factual accuracy**

- R8. The engineering CV must emphasize relevant mechanical roles and skills while retaining recent IT roles as compressed entries in truthful reverse chronology.
- R9. Support an engineering-led headline and introduction without changing actual employment titles, dates, qualifications, or achievement attribution, and without inventing experience or current proficiency.

**Application continuity**

- R10. The candidate must manually choose the profile for a new application before its documents are generated, and the selected profile must be visible with that application.
- R11. CV regeneration and initial or later cover-letter generation must use the application's selected profile and its eligibility rules unless the candidate explicitly changes the selection.
- R12. Treat existing applications without a recorded profile as IT unless the candidate explicitly changes them, without rewriting existing document files merely because profiles are introduced.

**One-time preparation**

- R13. Extract engineering facts from the candidate's old CV and obtain their confirmation before adding them to the shared master, leaving unknown details unclaimed rather than inferring them.

### Key Flows

- F1. Prepare the engineering source material.
  - **Steps:** Candidate supplies the old CV; the assistant extracts roles and supporting facts; the candidate confirms or corrects the extraction; approved facts enter the master under R2 and R13.
  - **Outcome:** Both profiles can draw on the same factual record without broadening IT eligibility.

- F2. Prepare an application.
  - **Steps:** Candidate selects a profile under R10; eligible source content is assembled under R3; CV and letter are tailored to the vacancy; outputs are checked under R7.
  - **Outcome:** Documents follow the chosen profile's content and presentation rules, per R4–R9.

- F3. Revisit an application.
  - **Steps:** Candidate regenerates a CV or requests a letter; the application selection is resolved under R11–R12; generation and checks follow F2.
  - **Outcome:** Working on an application of the other type does not change this application's profile.

### Acceptance Examples

- AE1. **Covers R2–R5, R7.** Given a master containing a pre-2019 mechanical role, mechanical-only CAD skills, and recent IT work, generating an IT CV excludes the mechanical role and CAD skills while retaining IT content.
- AE2. **Covers R6–R7.** Given the existing IT education and expanded engineering education, IT retains its original single MSc entry without the added bachelor's degree, thesis, specialization, or changed presentation; engineering shows the two expanded degrees, and the retained IT degree is not flagged as engineering spillover.
- AE3. **Covers R8–R9.** Given confirmed mechanical achievements and recent IT roles, the engineering CV gives relevant mechanical work more detail than unrelated IT work while keeping the actual employment titles and chronology accurate.
- AE4. **Covers R10–R11.** Given an engineering application followed by a separate IT application, regenerating the first application's CV or generating its letter still uses Mechanical Engineering.
- AE5. **Covers R2, R12.** Given an existing application without profile metadata, adding engineering content to the master does not change its IT selection or broaden the eligible input on regeneration.
- AE6. **Covers R3, R7.** Given the job description requests a mechanical skill excluded from the IT profile, the generator cannot borrow it from engineering-only facts; any such generated claim is identified as a violation.
- AE7. **Covers R13.** Given an old CV names a mechanical role but gives no quantified outcome, the import does not invent a metric, and the candidate reviews the available facts before they enter the master.

### Scope Boundaries

- Includes CV and cover-letter consistency under the same profile selection.
- Does not include automatic profile selection, dual-profile preview workflows, or a reusable file-import feature.
- Does not include interview-generation redesign, job-discovery or match-scoring changes, source snapshots, revision history, or automated learning from edits.
- Does not introduce a new CV layout or general-purpose profile editor; the exact selection surface and content-maintenance mechanism belong to implementation planning.

### Dependencies and Assumptions

- The candidate has supplied the old CV and confirmed the Life Cycle Data Engineer end date as March 2019; the private extraction awaits final review before merging.
- Existing IT source facts remain usable; imported engineering facts require candidate confirmation under R13.
- The one-time content import can follow software planning, but a meaningful engineering-CV trial requires those confirmed facts.

### Sources

- [Dual-CV ideation](../ideation/2026-10-19-it-mechanical-cv-ideation.html): evidence, candidate approaches, and tradeoffs preceding the confirmed profile rules in this contract.

---

## Planning Contract

**Product Contract preservation:** R6 and AE2 refined by the candidate's explicit education direction: IT stays as is and engineering uses the expanded education; other requirement and acceptance IDs retain their meaning. The two planning-owned questions are resolved by KTD1–KTD4.

### Key Technical Decisions

- KTD1. **Explicit profile policies inside the shared master; a pure, allowlist-based projection module.** Add `cv_optimizer/profiles.py` to resolve `it` and `mechanical_engineering`, validate references, and assemble the eligible generator input for R1–R6. Keep existing factual arrays and string achievements intact for current readers; profile metadata selects facts rather than maintaining duplicate biographies. No default inclusion of unselected or newly added facts.
  - Give experience and education records stable IDs; select role achievements by exact source-string references within a role and skills by category plus exact source value. Reject duplicate IDs, dangling references, and ambiguous selections; editing referenced text requires updating its selector. Do not use array indices, title heuristics, or wildcard “all future achievements” selectors.
  - Each profile supplies an approved headline, summary, role-detail policy, and explicit selections of other narrative-bearing sections, including community, hobbies, and certifications where present. Validate copied values against the source. Contact fields, language entries, and consent text use explicitly approved shared fields; an unknown source field is never copied automatically.
  - Use explicit education views under R6: preserve the current IT entry and its stored values, and select the expanded degree records/details only for engineering. Do not globally overwrite IT education with the imported master's dates or add the bachelor's degree to its projection. A role selected for engineering can expose only an approved subset of its IT achievements. Profiles need not share identical subsets.
  - Return eligible facts and presentation rules separately from checker-only exclusion descriptors. Generation serializes only the eligible facts; the full master, other profile summaries, and exclusion descriptors never enter its prompt.
  - Require prepared profile metadata before generation; missing or invalid policy produces an actionable configuration error, not an unrestricted-master fallback. U6 establishes the initial approved IT projection before this feature is enabled against the personal master. Engineering remains unavailable until its confirmed source facts and positioning exist under R13.
  - This is a compatibility extension of the source format, not a new source-of-truth service. A schema Bake-off is unnecessary: keeping existing factual containers avoids breaking matching readers while explicit selectors meet the confirmed exclusion rule. (Governs R1–R6, R8–R9; session-settled: user-approved — chosen over independently maintained full master files: shared facts with separate emphasis.)

- KTD2. **Store application selection without changing public tuple shape.** Add nullable `cv_profile` and an integer `cv_profile_revision` to applications; only `it`, `mechanical_engineering`, or unselected are valid stored selection states. On the one-time column-add migration, backfill then-existing rows to IT under R12; future inserts without a choice remain unselected.
  - Run profile migration after the existing AUTOINCREMENT rebuild, using schema inspection and a transaction; repeated initialization must not backfill newly unselected drafts. Do not swallow genuine migration failures. Preserve profile columns if a future legacy rebuild encounters them.
  - Replace application `SELECT *` tuple reads with the existing explicit nine-column projection in the existing order. Fetch profile metadata through dedicated accessors and add it to dictionary read models; avoid changing interview/edit/remove tuple consumers for a document-only feature.
  - Add a transactional selection setter that increments the revision and explicitly clears both ready-path columns only on a real profile change. Preserve files and status history. Selecting the same value or cancelling does nothing.
  - Profile is not part of duplicate identity: keep company/role/source dedupe semantics. The shared source path still comes from configuration or an existing per-call override; either source must pass KTD1. (Governs R10–R12.)

- KTD3. **One resolution boundary for all document paths, with manual selection at existing surfaces.** Initial tracking, CV regeneration, and initial/later letters resolve the application's selection before calling the generators; never use a mutable global current profile.
  - `TrackRequest` and direct new `track()` calls require a known explicit profile, with missing/null/empty/unknown values rejected before scheduling generation or inserting the application. This intentionally changes the old creation-request contract to satisfy R10; do not silently default old clients to IT.
  - Add one unselected-by-default selector to the extension, shared by extracted-job and manual-entry submission. In the TUI, show selection in the detail panel and add a small selection/change action using existing Select-modal conventions.
  - Discovery keeps its existing raw draft-only INSERT; the nullable profile field leaves new drafts unselected. The first CV or first letter action prompts for selection; cancellation leaves the draft unchanged. Direct ID-only generation of an unselected draft fails with a selection-needed message.
  - Selecting a profile does not automatically regenerate documents; the existing generation actions remain explicit. Explain invalidated ready paths when changing selection under KTD2. (Governs R10–R12; session-settled: user-directed — chosen over automatic or suggested selection: the candidate chooses the intended application narrative.)

- KTD4. **Profile-aware prompts and an independent content checker.** Preserve existing Markdown sections and language handling; replace conflicting current-title/recency assumptions with profile presentation rules for R8–R9. Keep exact historical titles and own-role achievement attribution, and do not require a software tech stack in a mechanical accomplishment.
  - Apply R6 inside the existing Education section: retain the current concise IT formatting and omit its attendance dates as before; engineering may show the supplied degree dates, specializations, and theses. Replace the prompt's unconditional education date omission with this profile-dependent rule.
  - Add `cv_optimizer/document_validation.py` and `cv_optimizer/prompts/validate_document.md`. Check cleaned CV and letter Markdown before rendering. Deterministic checks identify unambiguous excluded role/skill occurrences in factual sections; a separate LLM call checks claim meaning, attribution, and unsupported proficiency against allowed facts and checker-only excluded fact descriptors.
  - The checker receives the approved education facts and distinguishes an academic qualification from a claim of mechanical employment or current tool proficiency. Do not ban words such as “mechanical” globally or reject the vacancy's target title in the letter's subject line as a candidate claim.
  - Use the configured provider/model and validate a small JSON verdict with a boolean result and quoted violations. A rejection, missing/malformed verdict, or checker error fails the attempt; never infer approval from absent findings or a transport success. Return document type and actionable violation text to callers.
  - No automatic rewrite loop or new provider is added. Preserve the existing generator's bounded empty-output retry independently. This adds one checker completion per generated document; semantic checking reduces, but cannot mathematically eliminate, false negatives. (Governs R7–R9; session-settled: user-approved — chosen over keyword-only checks: paraphrased engineering spillover also needs checking.)

- KTD5. **Publish only checked documents; preserve prior valid replacements.** Introduce a small document-publication helper in `cv_optimizer/documents.py`, shared by tracker CV and letter paths. Generate and check in memory, render temporary Markdown/PDF files beside the destination, then promote the pair and update the document path only after success.
  - Capture the profile and revision before generation. At publication, acquire a short write transaction, re-read both, and reject a changed revision before any destination replacement. Selection updates use the same transaction discipline. The revision prevents IT→engineering→IT changes from admitting stale in-flight work.
  - Back up an existing pair temporarily during promotion and restore it on a caught rename/write/database failure; clean temporary files. On same-profile replacement failure retain prior valid files/paths and report failed replacement explicitly. On a profile change the old files remain on disk but paths stay unset until newly checked documents are published.
  - Keep `track()`'s returned application ID and tracked draft on generation failure. The server's completion notification must inspect actual per-document publication outcomes: tracked only, CV ready with letter failure, or both ready. An accepted request is not proof of completion.
  - Existing legacy paths remain grandfathered under R12, not retroactively certified as checked. Migration alone performs no document generation or file rewriting. No history system or crash-atomic filesystem/database transaction is promised. (Governs R7, R11–R12.)

### High-Level Technical Design

**Component and data-flow sketch.** KTD1, KTD3, and KTD4 define the allowed boundaries; only the projection crosses into the writing prompt.

| Source | Destination | Payload |
|---|---|---|
| Extension or TUI choice | Application storage | Selected profile under KTD2–KTD3 |
| Application storage and configured master | Profile resolver | Choice/revision plus factual source and profile policy |
| Profile resolver | CV or letter generator | Eligible facts and selected presentation rules only |
| Generator and profile resolver | Document checker | Draft, allowed facts, approved education, exclusion descriptors |
| Checker-approved draft | Staged renderer and publication | Markdown/PDF associated with captured selection revision |

**Generation protocol sketch.** The tracker owns orchestration, and the publication helper owns replacement and path writes.

1. Resolve application selection/revision and validate the projected source.
2. Generate the requested document from the eligible projection.
3. Check the document and render the temporary pair.
4. Recheck the selection revision inside the publication transaction.
5. Promote the pair and persist the ready path; on failure follow KTD5 without claiming readiness.

**Selection/readiness lifecycle sketch.** Ready state is derived from valid path publication, not a new application status.

| Starting state | Action | Result |
|---|---|---|
| Existing pre-feature row | One-time migration | IT selected; saved files unchanged |
| New discovery draft, unselected | Generate CV or letter | Selection requested; cancellation leaves it unselected |
| Selected, no ready documents | Successful generation/check/render | Requested document ready for current revision |
| Selected, documents ready | Choose other profile | Revision increments; both ready paths cleared; files retained |
| Selected, prior document ready | Failed same-profile replacement | Prior path retained; replacement failure reported |

**Entry-point decision matrix.** This distinguishes old stored applications from new requests rather than treating every missing value as IT.

| Entry | Selection input | Handling |
|---|---|---|
| Updated extension tracking | Explicit known value | Persist and generate |
| API/direct new tracking | Missing/null/empty/unknown value | Reject before generation/insert |
| New discovery import | None | Persist draft with unselected profile; no documents |
| Existing legacy row | Originally absent profile | IT via migration |
| Regeneration/later letter | Application selection | Reuse stored selection; reject unselected/invalid state |

### System-Wide Impact and Boundaries

- SQLite tuple compatibility matters to tracker edits, removal, interview preparation, and tests; KTD2 preserves their public nine-field shape.
- Matching/discovery currently consume the master independently and hash its factual projection (`cv_optimizer/matching.py` and `cv_optimizer/discovery/service.py`). Adding engineering facts may change scores/cache identity; profile-aware scoring is outside this plan, as confirmed.
- Interview preparation continues using its current source path and prompts; this work does not make it profile-aware.
- Correctness checks add latency and provider usage under KTD4. Unit and integration tests use synthetic candidate facts and fake completions, never paid network calls or the personal master.
- No automatic correction loop, source snapshots, or profile history is built: failures can be surfaced for explicit correction, and historical reproducibility was not requested.
- General migration cleanup and a repository-wide conversion to dictionary models are not built; only the compatibility seams required by KTD2 are touched.

### Sequencing and Research

U1 and U2 establish independent source and storage boundaries; U3 depends on U1; U4 integrates U1–U3; U5 exposes U2–U4; U6 prepares candidate content and final acceptance after U1–U5.

- `cv_optimizer/optimizer.py` and `cv_optimizer/cover_letter.py` serialize their input dictionaries; preserve their language and empty-response behavior while changing their input boundary.
- `cv_optimizer/tracker.py` owns the three document paths and catches initial generation failures; `server.py` currently announces both ready after receiving an ID. KTD5 addresses this directly.
- `cv_optimizer/db.py` contains additive migrations followed by an explicit AUTOINCREMENT rebuild and positional reads. Follow existing transaction helpers but use explicit schema checks for the new migration.
- [SQLite ALTER TABLE](https://www.sqlite.org/lang_altertable.html) and [PRAGMA table_info](https://www.sqlite.org/pragma.html#pragma_table_info), consulted through Context7, support additive migration with schema inspection. KTD2 uses nullable selection plus a one-time explicit backfill instead of a database default that would silently select IT for future drafts.
- Existing patterns: `tests/conftest.py` isolates the DB/application root and synthetic master; `tests/test_source_persistence.py` covers legacy schemas and tuple order; `tests/test_tui_pagination.py` drives Select modals with Textual's pilot.

### Deferred Execution Details

- Validate the checker response on the configured provider during an authorized manual smoke run; provider failure remains a failed check under KTD4, never a bypass.
- Historical role facts have been extracted from the supplied old CV, with the candidate-confirmed March 2019 end date replacing its historical “present” label. Final candidate review remains under R13; do not mark U6's personal-content acceptance complete before it.

---

## Implementation Units

### U1. Define profile policy and source projection

**Goal:** Produce an eligible, source-backed input for either document profile.

**Requirements:** R1–R6, R8–R9; F1–F2. **Dependencies:** None.

**Files:** Create `cv_optimizer/profiles.py` and `tests/test_cv_profiles.py`; extend `master_cv.example.json` with synthetic dual-career facts and profile policy.

**Approach:** Implement KTD1 as a pure resolver with a documented prepared-source contract. Provide selected presentation rules and checker descriptors without mutating the canonical master. Keep the example's factual string containers compatible with existing matching readers.

**Patterns to follow:** JSON source fields in `master_cv.example.json`; strict configuration errors in `cv_optimizer/discovery/config.py`; synthetic fixtures in `tests/conftest.py`.

**Test scenarios:**
1. Covers AE1–AE2. Project a mixed synthetic master to IT; mechanical jobs/skills are absent and its existing education is unchanged despite the expanded engineering data.
2. Covers AE3. Project engineering with detailed mechanical roles and approved brief IT selections; preserve their facts and date order.
3. Covers AE5. Add an unselected engineering fact after IT preparation; IT output remains unchanged.
4. Missing policy, duplicate role IDs, unknown profile, or dangling/edited achievement selectors fail without returning raw source as fallback.
5. Exclude an engineering-only summary, community entry, hobby, or unknown extra field; preserve the original master unchanged.

**Verification:** The generator-facing projection contains only selected source facts, with metadata and other-profile narrative absent.

### U2. Persist profile choice with legacy compatibility

**Goal:** Distinguish legacy IT applications, explicitly selected applications, and newly unselected drafts.

**Requirements:** R10–R12; F3. **Dependencies:** None.

**Files:** Modify `cv_optimizer/db.py`; add `tests/test_profile_persistence.py`; extend `tests/test_source_persistence.py` and `tests/test_discovery_importer.py` only for affected compatibility cases.

**Approach:** Implement KTD2 using existing DB connection helpers and explicit application projections. Add selection/revision accessors, transactional setter, and dictionary metadata. Preserve the discovery raw INSERT contract through nullable metadata rather than changing discovery selection behavior.

**Execution note:** Characterize old tuple order and both legacy schema variants before changing application storage.

**Test scenarios:**
1. Covers AE5. Fresh/current/non-AUTOINCREMENT legacy databases initialize repeatedly without losing paths, statuses, source, or tuple order.
2. After the first migration, a new raw-inserted draft remains unselected across later `init_db()` calls.
3. Covers AE4. Separate applications retain independent selections and revisions.
4. Changing selection clears both ready paths and increments revision in one transaction; same-profile selection changes neither.
5. Unknown stored selections fail resolution rather than silently becoming IT; dedupe identity is unchanged.

**Verification:** Existing positional consumers still receive exactly nine fields, and new selection state survives initialization without file mutation.

### U3. Apply presentation rules and validate generated claims

**Goal:** Generate the intended career narrative and detect prohibited content before rendering.

**Requirements:** R3–R9; AE1–AE3, AE6. **Dependencies:** U1.

**Files:** Modify `cv_optimizer/optimizer.py`, `cv_optimizer/cover_letter.py`, `cv_optimizer/prompts/optimize.md`, and `cv_optimizer/prompts/cover_letter.md`; create `cv_optimizer/document_validation.py`, `cv_optimizer/prompts/validate_document.md`, and `tests/test_document_validation.py`; extend `tests/test_cover_letter.py` and `tests/test_language.py` where their generator contracts change.

**Approach:** Enforce KTD1 at the public generator-input boundary and implement KTD4. Reuse completion configuration and cleanup behavior; do not expose a public raw-master bypass for document generation. Keep validation independent from the writing prompt and bind its verdict to the specific document passed to it.

**Test scenarios:**
1. Covers AE1, AE6. Capture fake completion requests: excluded facts and other-profile summaries never enter CV or letter writing messages, including when the JD requests an excluded skill.
2. Covers AE2. Preserve concise IT education in English and Polish, render the expanded engineering degrees only in engineering, and reject fabricated mechanical employment or unsupported current CAD proficiency.
3. Covers AE3. Engineering instructions resolve current-title/recency conflicts while retaining source-backed historical titles and available achievements.
4. A paraphrased excluded achievement is rejected through a stubbed semantic verdict; an exact excluded skill is caught without falsely banning the degree or letter target-title subject.
5. Malformed verdict, missing result, checker timeout, and a negative result each fail rather than approving output.
6. Existing empty-response retry, heading/language handling, and Markdown cleanup continue to behave as before.

**Verification:** Source projection and verdict handling are proven separately; tests do not present a stubbed model's semantic judgment as proof of real-model reliability.

### U4. Integrate checked publication throughout the tracker

**Goal:** Publish only valid documents associated with the application's current selection.

**Requirements:** R3, R7, R10–R12; F2–F3. **Dependencies:** U1–U3.

**Files:** Modify `cv_optimizer/tracker.py` and completion reporting in `server.py`; create `cv_optimizer/documents.py` and `tests/test_profile_generation.py`; use existing renderer boundaries in `cv_optimizer/generator.py` and `cv_optimizer/cover_letter.py` without redesigning their layout.

**Approach:** Wire KTD3–KTD5 through initial CV, regeneration, initial letter, and later letter. Keep application creation/status semantics and ID return intact. Stage and restore files around publication, and make server notifications reflect actual outcomes rather than the returned ID.

**Execution note:** Add characterization coverage for the currently untested tracker-generation catches and path-write ordering before changing them.

**Test scenarios:**
1. Covers AE4. Interleave engineering and IT applications, then regenerate the first CV and its later letter; capture the correctly selected inputs at every boundary.
2. Covers AE5. A migrated application regenerates as IT after master enrichment, without rewriting its files during migration.
3. Failed validation on a new attempt leaves no ready path or final artifact; the tracked draft remains recoverable.
4. Rendering or promotion failure during same-profile replacement preserves the prior valid Markdown/PDF pair and path, and reports failed replacement.
5. Change selection while generation is in flight, including changing away and back; the stale revision cannot publish.
6. Initial CV failure skips the initial letter as before; CV success with letter failure produces a partial-success notification, not “both ready.”
7. A master-path override still passes projection/checking and cannot replace the persisted profile choice.

**Verification:** Tracker tests stub paid services and inspect file/DB outcomes, not just mocked helper calls; one synthetic PDF integration exercises real rendering after a positive check.

### U5. Expose manual choice in extension and TUI

**Goal:** Make selection explicit before new generation and visible when revisiting an application.

**Requirements:** R10–R12; F2–F3. **Dependencies:** U2, U4.

**Files:** Modify `server.py`, `extension/popup.html`, `extension/popup.js`, `cv_optimizer/tui/app.py`, and `cv_optimizer/tui/screens/modals.py`; create `tests/test_profile_requests.py` and `tests/test_tui_profiles.py`.

**Approach:** Implement the existing-surface changes in KTD3 with keyboard-accessible controls. Pass the request field through the scheduled background task to tracker. Reuse modal confirm/cancel and selection-preserving refresh; avoid a new page, CLI command family, or general profile editor.

**Patterns to follow:** Extension's shared `postTrack`; existing `ModalScreen`/`Select` callbacks; TUI `run_test()`/pilot in `tests/test_tui_pagination.py`.

**Test scenarios:**
1. New creation rejects omitted/null/empty/unknown profiles before background scheduling; both allowed values survive request→runner→tracker propagation.
2. Both extracted-job and manual extension flows require and send the same explicit selection.
3. First CV and first letter actions on an unselected imported draft prompt for selection; cancellation makes no request or state change.
4. Covers AE4. Detail shows the stored selection; changing another application does not change it.
5. Profile change invalidates displayed document readiness without deleting files; selecting the same profile preserves it and table cursor selection.

**Verification:** Model/handler tests use the current request classes and a recording background-task collector without adding an HTTP testing dependency solely for this feature; Textual pilot and extension manual smoke prove the actual user controls.

### U6. Prepare candidate content and document usage

**Goal:** Make the two profiles usable with confirmed career facts and explain the new workflow.

**Requirements:** R1–R6, R8–R13; F1, AE7. **Dependencies:** U1–U5; candidate confirms the final extraction for the personal-content portion, using the already-confirmed March 2019 end date.

**Files:** Update `README.md` and `master_cv.example.json`; update local `master_cv.json` only with reviewed candidate facts and profile policy. Do not add the old personal CV or extracted drafts to version control.

**Approach:** Establish the current IT selections before importing mechanical history under KTD1. Review the extracted old-CV data with the candidate under R13, then add its approved facts and engineering positioning. Preserve IT education and configure the engineering education view under R6. Explain selector maintenance, request-contract change, legacy IT handling, checker failures, and source-enrichment impact on matching.

**Test expectation:** No new unit tests for documentation or copying reviewed personal facts; behavior is covered by U1–U5. Perform the acceptance checks below using synthetic source first, then candidate-approved content when available.

**Verification:** Candidate compares the two rendered versions: IT satisfies AE1–AE2 and engineering satisfies AE2–AE3; unavailable dates, metrics, or tools remain unclaimed under AE7. While extracted facts await final candidate review, report personal-content acceptance as pending rather than inventing content or declaring the engineering CV complete.

---

## Verification Contract

No tests or app execution were performed during planning. Run the following during implementation with isolated fixtures and stubbed generation/checker calls.

| Gate | Command or method | Passing evidence |
|---|---|---|
| Profile projection | `python3 -m pytest tests/test_cv_profiles.py -q` | U1 selectors and exclusion boundary |
| Storage compatibility | `python3 -m pytest tests/test_profile_persistence.py tests/test_source_persistence.py tests/test_discovery_importer.py -q` | U2 migrations, tuple shape, new draft state |
| Generation/checking/publication | `python3 -m pytest tests/test_document_validation.py tests/test_profile_generation.py tests/test_cover_letter.py tests/test_language.py -q` | U3–U4 verdict failures, application isolation, replacements |
| Selection surfaces | `python3 -m pytest tests/test_profile_requests.py tests/test_tui_profiles.py tests/test_tui_pagination.py -q` | U5 propagation, cancellation, visible state |
| Full regression suite | `python3 -m pytest tests/ -q` | Existing matching, discovery, edit, and rendering contracts still pass |
| Extension smoke | Both extraction and manual entry against local API | Explicit choice reaches stored application; omitted choice is blocked |
| Rendered acceptance | Synthetic dual-career CVs, then approved candidate source | AE1–AE3, AE7 visibly hold; first page establishes selected career |

Use shared `temp_db`, `temp_apps_dir`, and synthetic master fixtures. Do not call the real matching service from tracker tests. An optional authorized real-model smoke can evaluate checker behavior but does not replace deterministic failure-path tests or candidate review.

## Definition of Done

- U1–U5 meet their verification outcomes and the applicable regression gates pass.
- Every new creation/generation surface enforces R10; stored legacy behavior and initial partial-success reporting follow KTD2–KTD5.
- The two profile outputs meet the linked acceptance examples without an unrestricted-master input path.
- The candidate-content portion of U6 is explicitly distinguished from software completion; complete it only after the supplied old CV's final extraction is reviewed.
- Documentation matches the implemented source format and selection controls.
- Temporary generation artifacts and abandoned experimental code are removed, and personal source material is kept out of committed fixtures.
