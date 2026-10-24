---
title: Baker CV Profile - Plan
type: feat
date: 2026-10-24
topic: baker-cv-profile
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Baker CV Profile - Plan

## Candidate revision after PR #6 (2026-10-24)

The candidate changed the presentation contract below. This revision supersedes
the earlier frequency/fixed-batch facts and the role-by-role chronology decisions
(R5, R8, R10 and the corresponding KTD3/KTD4 details):

- Use over 70 bakes, mostly country loaves, with batches of **up to** four loaves.
  Do not state a monthly schedule or a fixed number of loaves per bake. A bake
  means a baking session, not a single loaf.
- Include frequently supplying bread for friends during group trips to a rented
  country house as hobby practice, not catering or commercial experience.
- Replace individual IT/engineering roles, employers and dates with one approved
  short career summary. The Baker writer receives that summary rather than role
  records; existing IT and engineering projections remain unchanged.
- Link the candidate's 5ciastek sourdough assistant at
  https://5ciastek.triggernote.app/ alongside the Instagram portfolio. Describe
  the self-built app's fermentation/hydration calculators, guided bake flow and
  bake history. The source repository is context, not a CV link.
- Omit LinkedIn and GitHub contact links from Baker CVs and cover letters.
- Portrait clarification: retain the configured candidate portrait on Baker CVs,
  just as on other profiles. The no-photos choice applies only to bread/Instagram
  portfolio imagery. This supersedes the earlier Baker photo suppression in
  KTD5 and its implementation/verification notes below.
- Polish wording revision: write directly for a Polish bakery, using natural
  terminology and a single clear hobby statement rather than literal English
  phrasing and repeated disclaimers. Use O mnie, Domowy wypiek chleba,
  Dotychczasowa praca zawodowa and Wykształcenie as headings. Legacy headings
  remain renderable/checkable. This changes presentation instructions, not master
  facts; use the candidate's current Baker career summary without restoring
  removed background or portfolio descriptions.

## Goal Capsule

- **Objective:** The candidate can apply for beginner-baker and trainee roles with documents that present their home baking practice, training, and previous work history accurately.
- **Means:** A third selectable Baker profile for CV and cover-letter generation (KTD1–KTD5).
- **Product authority:** The confirmed Product Contract below defines the current work; bakery job discovery and scoring are outside its scope.
- **Open blockers:** None. Candidate-approved facts are recorded below; implementation choices remain for planning.
- **Execution:** Implement and verify the U-ID units below; the invoking pipeline owns completion and shipping.
- **Stop conditions:** Return upstream if repository evidence invalidates a settled product decision or authoritative career data cannot support R8–R9; do not invent replacements.

---

## Product Contract

### Summary

Add a Baker profile that foregrounds home baking practice, the CookUp bread workshop, and an Instagram portfolio link.
Retain previous employment as a brief chronology and the engineering degree as a concise entry.
Use the selected profile for both the CV and cover letter.

### Problem Frame

The candidate is pursuing beginner-baker work between bakery production assistance and a trainee position.
Their professional career is in IT and mechanical engineering, while their relevant baking practice has been purely a hobby.
Existing career-led narratives do not explain what they can already do with bread or why they are applying at entry level.

The candidate has maintained a home baking practice since early 2022, attended a bread workshop, and documented bakes on Instagram.
That material supports an entry-level application, but it does not establish commercial production experience or a professional baking qualification.

### Key Decisions

- **Documents-only scope.** Governs R1–R3. (session-settled: user-directed — chosen over extending discovery and scoring: the requested outcome is a selectable profile for CVs and cover letters.)
- **Home practice is distinct from paid work.** Governs R4–R7. (session-settled: user-approved — chosen over presenting hobby baking as employment: the candidate confirmed that the baking was purely a hobby.)
- **Keep a brief employment chronology.** Governs R8. (session-settled: user-approved — chosen over omitting unrelated employment: work history should remain visible without displacing baking.)
- **Keep concise degree information.** Governs R9. (session-settled: user-directed — chosen over leaving formal education off: the candidate wants the engineering degree retained.)
- **A linked, text-led portfolio.** Governs R10–R11. (session-settled: user-approved — chosen over embedded photos or photograph-derived skill claims: the confirmed facts and Instagram link are sufficient.)
- **Baker-specific facts stay in their profile.** Governs R12. (session-settled: user-approved — chosen over sharing new baking content across profiles: IT and engineering documents should retain their existing narratives.)

### Requirements

**Selection and application continuity**

- R1. Offer Baker alongside IT and Mechanical Engineering wherever an application profile can be selected or displayed.
- R2. Use the application's explicitly selected Baker profile for initial and regenerated CVs and cover letters under the existing per-application selection behavior.
- R3. Preserve existing application selections and document-readiness behavior when adding Baker, including leaving unselected applications unselected.

**Baking practice and training**

- R4. Foreground a distinct home baking practice section on the Baker CV, keeping it separate from paid employment.
- R5. Prepare Baker source content from the candidate-approved facts in the table below, preserving their hobby context and approximate frequency.
- R6. Present the CookUp attendance as a baking workshop rather than a certification, apprenticeship, or professional qualification.
- R7. Tailor Baker documents for beginner-baker or trainee opportunities without converting hobby duration or workshop attendance into professional experience, commercial production proficiency, or unconfirmed credentials.

**Career and education**

- R8. Retain the candidate's existing IT and mechanical-engineering employment as brief title, employer, and date entries under other employment, using the authoritative career record without detailed technical achievements.
- R9. Retain the existing engineering degree as a concise degree-and-university entry, omitting specializations and thesis details.

**Portfolio and source eligibility**

- R10. Include a clearly identified baking portfolio link to https://www.instagram.com/piekarskocukierniczy/ in the Baker CV without embedding photographs.
- R11. Use only candidate-confirmed baking claims in generation, treating Instagram photographs and the current workshop syllabus as supporting context rather than automatic proof of additional skills.
- R12. Keep the new practice, workshop, portfolio link, and baking skills eligible only for Baker, preserving the existing IT and Mechanical Engineering selections and presentation rules.
- R13. Apply the existing profile-aware document checks to Baker content and exclusions, including the distinction between hobby practice, workshop attendance, and employment.
- R14. Retain the existing job-description-based Polish or English document generation behavior for Baker.

**Candidate-approved source facts for R5**

| Fact | Approved content |
|---|---|
| Target | Beginner baker, between bakery production assistant and baker apprentice/trainee |
| Practice context | Purely hobby home baking; no paid baking work reported |
| Start | Beginning of 2022; no exact month or day supplied |
| Frequency and batch size | Around once a month, four loaves per bake |
| Independently practised techniques | Maintaining a sourdough starter; mixing and fermenting dough; shaping loaves; baking country loaves |
| Workshop | CookUp “Chleby” bread-baking workshop, May 2026 cohort |
| Instructor | Piotr Bruś-Klepacki |
| Portfolio | https://www.instagram.com/piekarskocukierniczy/ |

The candidate confirmed May 2026 despite supplying a workshop URL with a November date selected.
No exact attendance day, formal certificate, sanitary clearance, commercial equipment experience, or commercial output volume was supplied.
These omissions are not claims that the candidate lacks them; R7 and R11 govern what may be asserted.

### Key Flows

- F1. Prepare the profile.
  - **Steps:** Use the confirmed source facts under R5, preserve their distinctions under R4 and R6–R7, and select the existing career and degree content under R8–R9.
  - **Outcome:** Baker has an approved factual basis without changing the other profiles under R12.
- F2. Prepare a bakery application.
  - **Steps:** The candidate selects Baker under R1; generation uses R2 and R14; the CV foregrounds R4–R6 and includes R8–R10; the letter uses the same eligible facts under R7 and R11.
  - **Outcome:** The documents present a career changer seeking beginner work and undergo the checks under R13.
- F3. Revisit an application.
  - **Steps:** Regenerate either document under R2, or explicitly change the application's profile using the existing behavior preserved by R3.
  - **Outcome:** Editing or generating another application's documents does not alter this application's selection.

### Acceptance Examples

- AE1. **Covers R1–R3, R14.** Given an unselected application with a predominantly Polish bakery JD, selecting Baker enables CV and cover-letter generation in Polish; an existing IT application retains its selection.
- AE2. **Covers R4–R7.** Given the approved practice facts, the CV describes home baking since early 2022 and approximately monthly batches of four loaves, rather than claiming four years of professional bakery employment or daily production.
- AE3. **Covers R5–R7, R11.** Given the CookUp attendance and a current syllabus listing focaccia and burger buns, the documents can name the workshop but do not assert independent proficiency in those products without candidate confirmation.
- AE4. **Covers R8–R10.** Given existing employment and degree records, the Baker CV keeps brief career entries, a concise degree entry, and a clickable baking portfolio link, while giving baking practice the emphasis.
- AE5. **Covers R7, R11, R13.** Given a vacancy asking for commercial ovens, high-volume production, or sanitary clearance, the documents do not claim these solely because the JD requests them or the portfolio shows finished bread.
- AE6. **Covers R2–R3, R12–R13.** Given Baker facts added to the master record, regenerating an IT or Mechanical Engineering document excludes them; regenerating a Baker cover letter reuses that application's selected profile.

### Scope Boundaries

- Bakery job discovery, match scoring, and interview-generation changes are excluded.
- Automatic Instagram scraping, recurring synchronization, and a reusable social-media importer are excluded; the confirmed facts above are sufficient for this profile.
- A photo CV, a separately generated visual portfolio, and a portfolio website are excluded by R10.
- Reworking IT or engineering narratives is excluded by R12.
- Formal baking qualifications, food-safety training, and medical paperwork acquisition are not deliverables of this work.

### Dependencies / Assumptions

- Existing career and degree records remain authoritative for the content selected under R8–R9.
- The screenshot is supporting portfolio context; the candidate's explicit answers are the authority for skills, practice frequency, and hobby status.
- The workshop's live page may change. The confirmed May 2026 attendance takes precedence over its currently selected November offering.

### Outstanding Questions

- **Deferred to Planning:** Choose how to represent and select home practice, workshop attendance, and a profile-specific portfolio link without misclassifying them as employment or certifications.
- **Deferred to Planning:** Determine the integration and verification changes needed across existing profile selectors, generation, and content checks to satisfy R1–R14.

### Sources / Research

- Candidate answers and supplied Instagram screenshot: authority for the approved facts under R5.
- [CookUp “Chleby”](https://www.cookup.pl/p/baking-time/): workshop name, instructor, and published course context; attendance month and year were separately confirmed by the candidate.
- `docs/plans/2026-10-19-1239-feat-dual-cv-profiles-plan.md`: shared factual master, explicit profile selection, and eligible-source projection precedent.
- `docs/plans/2026-10-19-2326-feat-mechanical-cv-it-ledger-plan.md`: existing work on compressed unrelated employment; Baker's presentation is governed by R8 rather than inherited mechanically.
- `cv_optimizer/profiles.py`: current source eligibility and profile policy constraints; dedicated home-practice and workshop selections require planning.
- `cv_optimizer/tui/screens/modals.py`, `extension/popup.html`, and `server.py`: existing profile selection and validation surfaces.
- `cv_optimizer/tracker.py` and `cv_optimizer/language.py`: persisted profile use and JD-based document language behavior.

---

## Planning Contract

**Product Contract preservation:** Product Contract unchanged. Its Outstanding Questions are answered by KTD1–KTD5 below.

### Key Technical Decisions

- KTD1. **Add `baker` to the existing profile boundary without a database migration.** Extend name validation, the tracking request, extension options, and TUI labels; continue using the stored `(cv_profile, cv_profile_revision)` for both documents (R1–R3). `cv_optimizer/db.py` stores profile names as text, while `cv_optimizer/documents.py` checks the captured revision before publication. Do not alter defaults, backfill existing rows, or infer selection from a bakery JD. This instantiates the documents-only Key Decision. (session-settled: user-directed — chosen over discovery/scoring expansion: the user selected CVs and cover letters only.)
- KTD2. **Represent non-employment evidence as explicit selected snapshots.** Add canonical `home_practice`, `workshops`, and `portfolio_links` arrays with Baker-only optional policy selectors of the same names in `cv_optimizer/profiles.py` (R4–R7, R10–R12). Reuse `_snapshots` / `_select`: omission selects nothing, source order is retained, and duplicate, ambiguous, stale, wildcard, or unknown-field selectors fail closed. Each context records unselected entries in `excluded.sections`; writer payloads still receive only `facts` and `rules`. Reject these new selector keys on IT and Mechanical Engineering policies. This extends the existing community/certification snapshot pattern rather than inserting hobby records into employment or certification arrays. (session-settled: user-approved — chosen over employment/qualification packaging: the candidate reported only hobby practice.)
- KTD3. **Use existing empty-achievement brief roles and the concise degree view for Baker.** Select all authoritative career IDs with `detail: brief` and no achievements in the Baker policy; do not broaden the mechanical-only ledger override (R8–R9, R12). Select the existing concise engineering degree ID, and project only its ID, degree, and university for Baker in both document contexts. Put omitted academic fields in checker exclusions without treating the selected degree identity as excluded. Existing IT and engineering projections remain unchanged. (session-settled: user-approved — chosen over removing unrelated employment: the user wants a brief career chronology.) The retained concise degree also instantiates the degree Key Decision. (session-settled: user-directed — chosen over omitting the degree: the user requested it.)
- KTD4. **Give Baker an explicit section contract in both languages.** Its main column is Summary, Home Baking Practice, Workshops, Other Employment, Education, followed by the existing selected consent footer (R4, R6, R8–R10, R14). Portfolio is a labeled sidebar link alongside existing selected contact, skills, and languages. Map Polish headings to those same canonical sections: `Domowa praktyka piekarska`, `Warsztaty`, `Pozostałe zatrudnienie`, `Portfolio`. Recognize these exact headings before broad substring routing, especially `work` in Workshops. Treat Other Employment as the existing Experience content internally so employment checks keep applying. Conditional Baker rules override generic technical-recruiter, fixed-order, achievement-story, and keyword-placement instructions; IT/engineering keep their current section contracts. Preserve URL text through cleanup and render it as a clickable link, with a narrow link exception to the prompt's square-bracket prohibition if Markdown link syntax is used. This implements the text-led portfolio choice. (session-settled: user-approved — chosen over photo CVs and image-derived skills: the confirmed facts and link suffice.)
- KTD5. **Reuse advisory validation and publication, with Baker-aware semantics.** Extend the validator prompt to check R7, R11–R13 across both documents and languages, including missing required Baker CV sections and portfolio, inflated hobby frequency, workshop-to-credential promotion, and excluded technical achievements. Extend literal employment-section extraction for Other Employment and its Polish alias; do not build a brittle keyword detector for every paraphrase. Keep the existing advisory/incomplete outcomes and content-free notifications (R3, R13). Suppress the configured candidate photo at the Baker CV renderer call by supplying the existing explicit empty-photo override; do not mutate global settings or affect other profiles (R10).

### Source Shape

The following is a directional data-shape guide, not production JSON or a new importer:

- `home_practice`: records with `title`, `context`, `start_period`, `frequency`, `batch_size`, and `activities` (a string list). Preserve approximate dates and quantities as approved strings; `start_period` is “early 2022”, not a fabricated January date.
- `workshops`: records with `name`, `provider`, `attendance_period`, `instructor`, and optional `url`. Attendance is “May 2026”; no certificate or inferred syllabus outcomes are added.
- `portfolio_links`: records with `label` and `url`. The local Baker entry uses the approved Instagram URL under R10; the shipped example uses a synthetic `example.com` portfolio.
- Baking skills: add the confirmed techniques to a new canonical baking skill category, then explicitly select only those strings in Baker. Do not select the new category in existing profiles.
- `profiles.baker`: approved entry-level headline/summary plus required roles, skills, education selectors and the three new snapshot selectors. Keep home-practice frequency/context in selected facts rather than only in positioning prose.

Use explicit field allowlists and the repository's string/list/object validation, not arbitrary free-form policy content. No generic plugin registry or source-schema migration is needed: new arrays default to empty, and a master with only the two existing prepared profiles remains valid.

### High-Level Technical Design

**Component and data flow:** extension/TUI selection → stored profile and revision → tracker → profile resolver → selected facts/rules → CV or letter writer → advisory checker → renderer → revision-checked publication. Only the checker receives exclusions. The local master and synthetic fixture enter at the resolver; Instagram is a link, never an input-fetch stage.

**Document protocol:** capture selection → resolve a document-specific context → detect JD language → write and clean Markdown → check that exact Markdown → render staged files → publish only if the captured selection/revision still matches. The existing tracker and publisher own this protocol; Baker extends their inputs and renderer choice, not their transaction boundary.

**Selection lifecycle:** unselected → explicit Baker selection → generated ready paths; changing profile → revision increment and cleared ready paths; same-profile selection → no mutation. Cancellation leaves state intact. A stale in-flight result cannot restore readiness, including a Baker → IT → Baker switch.

**Schema and presentation boundary:** canonical home practice/workshops/links → exact Baker snapshots → distinct practice/training/portfolio sections; canonical employment → brief identity-only Baker entries → Other Employment; canonical concise degree → limited Baker academic projection → Education. These mappings never turn practice or training into employment or certification.

### Assumptions

- **Unvalidated presentation bet:** the KTD4 section labels and sidebar placement provide sufficient prominence for the portfolio. Validate layout with rendered documents; this does not change R10.
- **Unvalidated positioning bet:** an entry-level headline such as “Aspiring Baker” / “Początkujący piekarz” and a factual career-change summary express the approved target without claiming a qualification. Final wording remains bounded by R5–R7.
- **Execution prerequisite:** the ignored local `master_cv.json` is available to the implementing session. Its actual role and degree IDs must be read then; the synthetic IDs in `master_cv.example.json` are examples, not claims about the candidate.

### Research and Behavior Trace

- `cv_optimizer/profiles.py`: all supplied policies are validated, not just the requested profile. Optional sections already use exact snapshots, while skills use exact strings. New Baker metadata must therefore be valid even when generating IT documents.
- `cv_optimizer/tracker.py` `_generate_document`, `cv_optimizer/db.py` `set_application_profile`, and `cv_optimizer/documents.py` `publish_document`: selection is captured before writing; real changes invalidate both ready paths; staged publication checks revision under the write transaction and restores prior artifacts on caught promotion failures. Extend existing integration tests rather than introducing another lifecycle.
- `cv_optimizer/optimizer.py` and `cv_optimizer/prompts/optimize.md`: cleanup preserves links, but the prompt currently forbids square brackets and fixes output order. `cv_optimizer/language.py` fixes Polish headings. All three must agree with KTD4.
- `cv_optimizer/generator.py`: only fixed main/sidebar lists are rendered; unknown headings alone do not make a new section visible. Broad `work` normalization precedes all other English routing, and `photo_path=None` falls back to configured candidate photography. KTD4–KTD5 address both behaviors.
- `cv_optimizer/document_validation.py`: semantic checking is advisory and receives exclusions; literal CV checks currently inspect only `Experience` / `Doświadczenie`. KTD5 preserves those checks under the new visible employment label.
- `tests/test_profile_generation.py`, `tests/test_profile_requests.py`, and `tests/test_tui_profiles.py`: synthetic integration fixtures cover publication, request propagation, cancellation, and persisted selection. Extend them for Baker rather than relying on prompt snapshots alone.
- `PRODUCT.md`: reliability and fast document turnaround for a solo job-seeker support using the existing selection workflow. Reporting derives profile filters dynamically; no new reporting feature is needed.

No external research is needed for this local profile extension. Reuse the existing snapshot mechanism; snapshot selection versus new ID-based non-employment entities does not warrant a bake-off because there are no cross-record relationships or independent update lifecycle here. Encoding these facts as employment, certifications, or global contact data fails R4, R6, or R12.

### System-Wide Impact and Boundaries

- API, extension, and TUI must accept and display the same third profile. The existing API carries generation selection; no new agent API, CLI profile command, or tool registry is required.
- New canonical baking skills may be visible to existing whole-master consumers. Do not change scoring, discovery, or interview behavior or add profile awareness there; document that distinction from document eligibility under R12.
- No profile database migration, existing-document rewrite, network importer, image processing, generic education selector framework, or automatic retry layer is planned. Existing mechanisms cover the required use; revisit only if execution reveals a concrete contract gap.
- The implementation must update ignored `master_cv.json` for real use and separately update synthetic `master_cv.example.json` for shipped code/tests. Never force-add the personal master, `candidate.jpeg`, or generated candidate documents. Do not copy private career/contact values into tests or new documentation.

### Sequencing and Deferred Implementation Details

U1 establishes projection and source eligibility. U2 and U3 depend on U1 and can then proceed independently. U4 integrates them. U5 prepares the actual local profile and usage documentation after the schema and output contracts are stable.
Exact helper names and final translated prose are execution details. Runtime layout, PDF link annotations, and provider output quality require verification during implementation, not assumptions of success here.

---

## Implementation Units

### U1. Prepare Baker facts and preserve existing projections

**Goal:** Resolve Baker contexts from the synthetic master while keeping employment, training, and practice distinct.

**Requirements:** R4–R12; F1; KTD2–KTD3.

**Dependencies:** None.

**Files:** `cv_optimizer/profiles.py`, `master_cv.example.json`, `tests/test_cv_profiles.py`.

**Approach:**
1. Add the Baker profile identity and the allowlisted snapshot records described by KTD2; keep pre-Baker masters valid.
2. Populate synthetic Baker sources/policy with fictional identity, workshop provider/instructor, and portfolio values. Use the Product Contract's structure and limitations without copying the real career record.
3. Apply KTD3 for Baker-only employment and education projection, recording excluded content for checking.

**Patterns to follow:** `_snapshots`, `_select`, `_record`, and `resolve_profile`; the example is the authoritative synthetic schema fixture.

**Test scenarios:**
1. Covers F1 / AE2. A prepared Baker master resolves the approved practice context, approximate start, frequency, and batch size in both document contexts, outside employment.
2. Covers AE3. Workshop selection resolves attendance only, without a certification or independently practised syllabus products.
3. Covers AE4. Baker selects all source employment identities with no technical achievements and only degree/university academic content.
4. Covers AE6. Adding all new facts leaves IT and engineering writer facts/rules unchanged; their checker exclusions include the new Baker-only records and skills.
5. A missing Baker policy fails only requests for Baker; old two-profile masters still resolve. Malformed supplied Baker metadata also fails an IT request under the existing all-policy validation contract.
6. Stale, duplicate, ambiguous, wildcard, and unknown-field snapshots fail closed; omitted selectors select nothing; source and returned contexts remain independent.

**Verification:** Projection tests establish all three profiles' eligible/excluded boundaries without personal data or paid model calls.

### U2. Produce and render Baker documents in English and Polish

**Goal:** Make Baker content visible in both Markdown and PDF with the hierarchy and source limits required by the Product Contract.

**Requirements:** R2, R4–R11, R14; F2; KTD3–KTD5.

**Dependencies:** U1.

**Files:** `cv_optimizer/prompts/optimize.md`, `cv_optimizer/prompts/cover_letter.md`, `cv_optimizer/language.py`, `cv_optimizer/generator.py`, `cv_optimizer/tracker.py`, `tests/test_profile_prompts.py`, `tests/test_generator.py`, `tests/test_language.py`.

**Approach:**
1. Add conditional Baker CV and letter instructions; resolve the fixed-order, language-heading, square-bracket, and technical-achievement prompt conflicts under KTD4.
2. Extend parser normalization and rendered section lists for practice, workshops, and portfolio while retaining Other Employment as canonical Experience.
3. Pass the explicit photo-suppression override only for Baker CVs under KTD5. Keep the publisher's two-argument renderer callback contract.

**Execution note:** Add characterization coverage for Workshops routing before modifying the broad heading parser.

**Patterns to follow:** existing bilingual heading tests, `PDFGenerator._parse_to_html_sections`, `_heading`, and fake-client prompt inspection.

**Test scenarios:**
1. Covers AE2 / AE4. English and Polish Baker Markdown renders practice before employment, the workshop separately, all brief employment entries, the concise degree, and a labeled portfolio.
2. Workshops and its Polish label never overwrite Experience; Other Employment and its Polish alias preserve all career entries and dates.
3. The portfolio target survives writer cleanup and appears as a clickable PDF link annotation, not merely extracted text. Use a synthetic URL.
4. A configured synthetic candidate image is absent from Baker PDFs, while existing profile photo behavior remains unchanged.
5. Covers AE3 / AE5. CV and letter writer payloads contain the same eligible baking sources but no exclusions or other-profile narratives; prompts forbid commercial/syllabus/qualification inflation in either language.
6. Existing English/Polish IT and engineering outputs retain their section routing, ledger behavior, and academic presentation.

**Verification:** Synthetic PDF text, section order, links, and images prove renderer behavior; fake-client tests establish writer instructions and payload isolation without treating mocks as proof of live model quality.

### U3. Expose Baker across selection and request boundaries

**Goal:** Select and display Baker through every existing application-profile entry point.

**Requirements:** R1–R3; F2–F3; KTD1.

**Dependencies:** U1.

**Files:** `server.py`, `extension/popup.html`, `extension/popup.js` (only if propagation needs adjustment), `cv_optimizer/tui/screens/modals.py`, `cv_optimizer/tui/app.py` (only if label handling needs adjustment), `tests/test_profile_requests.py`, `tests/test_tui_profiles.py`, `tests/test_tui_modals.py`, `tests/test_profile_persistence.py`.

**Approach:**
1. Add Baker to the request name constraint, shared TUI label map, and popup options; retain existing selection defaults.
2. Extend existing request/popup/TUI tests to select by profile value rather than assuming Mechanical Engineering is the last option.
3. Verify existing persistence behavior accepts Baker through shared validation, without schema changes.

**Patterns to follow:** `TrackRequest`, popup's shared submit path, `ProfileModal`, and existing database selection setter.

**Test scenarios:**
1. Covers AE1. Both popup capture modes submit `baker`; the request schedules generation with that exact selection. Missing, null, empty, and unknown names remain rejected before mutation.
2. A blank TUI selection cannot confirm; cancel/escape leaves the application unselected. Explicit Baker selection persists and displays “Baker” on first CV and first letter actions.
3. Covers F3 / AE6. Changing IT to Baker increments revision and clears both ready paths only for that application; selecting Baker again is a no-op.
4. Existing IT/engineering selections, unselected drafts, and the original one-time legacy migration behavior survive database reinitialization.
5. Popup capture retains its captured selection if the user changes the control while extraction is pending.

**Verification:** Isolated database, TUI pilot, and Node popup-listener tests demonstrate surface parity and unchanged selection semantics.

### U4. Integrate Baker checking and document lifecycle coverage

**Goal:** Verify initial and regenerated Baker documents against the captured profile without changing advisory readiness behavior.

**Requirements:** R2–R3, R7, R11–R14; F2–F3; KTD1, KTD5.

**Dependencies:** U2, U3.

**Files:** `cv_optimizer/prompts/validate_document.md`, `cv_optimizer/document_validation.py`, `tests/test_document_validation.py`, `tests/test_profile_generation.py`.

**Approach:**
1. Extend semantic-check instructions and literal employment heading recognition under KTD5.
2. Extend existing tracker integration fixtures to interleave Baker, IT, and engineering applications and inspect each writer/checker context.
3. Exercise actual PDF rendering with synthetic Baker writer responses and a fake checker; preserve publication failure and stale-selection behavior.

**Patterns to follow:** `ValidationResult`, `_employment_text`, fake semantic verdicts, and existing staged-publication integration tests.

**Test scenarios:**
1. Covers AE1 / AE6. Initial CV+letter, regenerated CV, and later letter use Baker's persisted selection and the detected Polish/English language after another profile's application is generated.
2. Covers AE5. Checker payload/instructions distinguish hobby practice, workshop attendance, and employment; supplied failing semantic verdicts flag professional-duration, daily-production, commercial-equipment, sanitary-clearance, and qualification claims without blocking publication.
3. Excluded employment titles under Other Employment / Pozostałe zatrudnienie trigger the same literal warnings as Experience; practice/workshop prose does not become employment by heading collision.
4. A checker outage or malformed verdict produces the existing incomplete advisory, publishes through the existing path, and keeps private excerpts out of user notifications.
5. Covers F3 / AE6. Switching Baker → IT or Baker → IT → Baker during writing/rendering rejects stale publication; another application's selection remains untouched.
6. An unprepared Baker master fails before writing/rendering and preserves the draft/readiness behavior; a renderer failure preserves prior artifact pairs and database paths.

**Verification:** The integration uses real resolver, database, checker boundary, and publisher with fake paid completions; at least one case uses real PDF generation.

### U5. Prepare the real local Baker profile and document usage

**Goal:** Make the feature usable with the candidate's local master while keeping shipped fixtures synthetic.

**Requirements:** R5–R12; F1–F3; KTD1–KTD4.

**Dependencies:** U1–U4.

**Files:** `master_cv.json` (ignored local data only), `README.md`, `master_cv.example.json` (schema example cross-check), `tests/test_cv_profiles.py` (existing synthetic verification).

**Approach:**
1. Read the local career and degree records; add only the approved R5 facts and Baker policy using their actual source IDs. Do not replace existing policy narratives, role records, shared contacts, or consent.
2. Record approximate practice and May 2026 workshop attendance exactly at their supplied precision; use the approved portfolio URL only in the local source/policy.
3. Update README's two-profile wording, API values, schema preparation, Baker section behavior, advisory checks, and local-versus-synthetic setup guidance. Explain that source edits take effect on regeneration rather than rewriting saved documents.

**Patterns to follow:** README's explicit prepared-profile documentation and the synthetic master fixture.

**Test scenarios:**
1. Covers F1 / AE2–AE4. A local preparation review against the R5 table finds all approved facts, actual career identities, and the retained degree without unsupported additions.
2. Covers AE6. Resolve local IT/engineering facts before and after enrichment to confirm their writer data is preserved; keep any comparison output private and do not add personal-data tests.
3. The shipped example resolves all three policies through the existing synthetic suite; repository changes contain no personal master, image, or generated documents.

**Verification:** A separate local source review and synthetic schema checks prove preparation. Representative local documents receive the manual checks in the Verification Contract; no private values are copied into reports.

---

## Verification Contract

Implementation verification uses the repository's `python3 -m pytest` workflow; this planning stage does not execute it.

| Gate | Scope | Completion evidence |
|---|---|---|
| Projection | `tests/test_cv_profiles.py` | Baker source selection and unchanged existing writer projections, with strict snapshot failures |
| Writing and language | `tests/test_profile_prompts.py`, `tests/test_language.py` | Approved-only payloads and consistent English/Polish section instructions |
| Rendering | `tests/test_generator.py` | New section order, real text and link annotations, no Baker photo, existing layouts retained |
| Selection | `tests/test_profile_requests.py`, `tests/test_tui_profiles.py`, `tests/test_tui_modals.py`, `tests/test_profile_persistence.py` | API/popup/TUI acceptance, cancellation, revisions, and old/unselected records preserved |
| Checking and publication | `tests/test_document_validation.py`, `tests/test_profile_generation.py` | Advisory outcomes, correct regeneration contexts, stale-result rejection, real Baker PDF publication |
| Regression | Full `tests/` suite, including existing ledger tests | No regressions outside Baker; Node-backed popup smoke actually runs rather than being silently skipped |
| Candidate use | Local master review and representative Polish and English Baker CV/letter pairs | R5 precision and hobby/workshop limits hold; career is brief; degree concise; portfolio clickable; no images; documents remain legible |

Use synthetic inputs and fake paid completions for automated coverage. Prompt inspection and mocked verdicts prove wiring and policy, not that a live LLM always obeys them. The representative document review must check AE1–AE6, including unsupported vacancy requests; fix prompt/output defects found there without turning advisory checks into hard gates. If provider access prevents this review, report it as unverified rather than claiming document quality from mocked tests.

No release-validation script or behavioral skill evaluation applies to this application feature; use the repository test workflow and document checks above. Source changes are additive and do not rewrite existing PDFs, Markdown, selections, or application history.

---

## Definition of Done

- U1–U5 meet their Verification outcomes, and R1–R14 / F1–F3 / AE1–AE6 are covered by the linked scenarios and candidate-use checks.
- Baker is selectable and usable for both initial and regenerated documents; existing IT/engineering and unselected application behavior remains intact.
- The actual ignored master is prepared for real use, while shipped example/test data remains synthetic.
- Automated gates pass and representative document-review results are reported accurately, including any provider-dependent residual.
- README describes the three-profile contract and preparation requirements.
- Abandoned attempts, debug artifacts, unrelated refactors, and personal runtime files are absent from the shipped change.
