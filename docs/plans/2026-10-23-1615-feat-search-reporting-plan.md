---
title: Search Focus Reporting - Plan
type: feat
date: 2026-10-23
topic: search-reporting
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Search Focus Reporting - Plan

## Goal Capsule

- **Objective:** Help the solo job-seeker decide where to focus their job-search effort next using evidence from their recorded applications and discovered opportunities.
- **Means:** A local browser reporting overview with a decision brief, a Sankey summary, and detailed views for all seven selected reports.
- **Product authority:** The confirmed scope in this Product Contract governs the reporting workspace as one feature; the earlier ideation supplies evidence, not additional requirements.
- **Open blockers:** None.
- **Execution and handoff:** Implement the dependency-ordered units below, verify their outcomes, and ship through the authorized build/review/PR workflow.
- **Stop conditions:** Stop if implementation requires changing the settled Product Contract or if reporting cannot meet R4 without writing to the search record.

---

## Product Contract

### Summary

Build a read-only reporting workspace whose overview highlights evidence relevant to the next job-search decision.
Provide full channel, cohort, stage-loss, targeting, skill-gap, aging, and opportunity-inventory reports alongside an application Sankey.
Connect conclusions to their supporting charts and underlying records.

### Problem Frame

The user wants to know where to focus next, rather than only see how applications move through a funnel.
Recorded application volume, interview outcomes, match assessments and opportunity inventory offer different signals, with uneven coverage and observation time.
Automatic ghosted defaults, sparse source attribution and backfilled dates can make an attractive chart misleading unless its population and limitations are visible.

### Key Decisions

- **Overview with focused reports.** Governs R1–R3. This keeps a quick decision-oriented entry point while retaining analytical depth. (session-settled: user-directed — chosen over a report-only workspace and a single long review page: the user selected sketch B after seeing their navigation and maintenance tradeoffs.)
- **Prioritize where to focus next.** Governs R2, R14–R18. The user selected search-effort allocation over making the landing page primarily a daily application task list. (session-settled: user-directed — chosen over applications needing attention today: the user named where to focus next as the main decision.)
- **Read-only, evidence-based interpretation.** Governs R4, R7–R13, R25–R28. The confirmed scope keeps record management in the existing tools and avoids turning weak observations into explanations or prescriptions. (session-settled: user-approved — chosen over editing within the dashboard or presenting unsupported recommendations: the user confirmed the scope with these limitations visible.)
- **Keep all eight analytical views.** Governs R14–R22. The requested breadth is delivered through one workspace with shared definitions, rather than selecting only the highest-ranked ideation report.

### Requirements

**Workspace and navigation**

- R1. Provide a local browser overview with navigation to all seven detailed reports and the full Sankey view.
- R2. Lead the overview with a concise decision brief that identifies supported patterns worth investigating for search-effort allocation.
- R3. Include a Sankey summary on the overview with access to its full view.
- R4. Reading, filtering, navigating and refreshing reports must not change applications, assessments, discovery records or their histories.
- R5. Application reports must share an applied-date range, profile and source filter context, starting with all recorded application dates and all profiles and sources.
- R6. Show the active scope and data retrieval time, preserving the application filter context when moving between the overview and application reports.

**Definitions and evidence**

- R7. Use distinct applications with a recorded applied event as the default denominator for application-outcome rates, separating never-applied records from that population.
- R8. Distinguish current status from ever reaching a stage, using recorded chronology with a stable tie-breaker to resolve simultaneous status updates.
- R9. Describe unresolved ghosted records as “no recorded outcome” and expose their recorded age rather than presenting them as confirmed terminal ghosting.
- R10. Label elapsed-time metrics as recorded time and explain that activation, backfilling and undo can limit historical accuracy.
- R11. Show numerators, denominators and relevant coverage alongside comparisons, keeping missing sources, missing assessments and unknown evidence explicitly separate.
- R12. Conclusions must describe observed associations and their limitations rather than claim causality, employer rejection reasons or guaranteed future outcomes.
- R13. Use “insufficient data” when evidence cannot support a comparison or recommendation, retaining descriptive counts where available.

**The seven detailed reports**

- R14. The channel report must compare observed interview incidence by normalized recorded source and show source coverage, with recruiter-selection bias explicit.
- R15. The cohort report must compare interview attainment within 7, 14 and 30 recorded days by application cohort, marking follow-up windows that have not matured as unavailable rather than zero.
- R16. The stage-loss report must distinguish recorded progression, rejection, withdrawal and unresolved cases at recorded stages, separating rejections with no prior recorded interview from post-interview rejections.
- R17. The targeting report must compare observed interview incidence by match-score band and normalized assessed role family, exposing assessment coverage, timing and scoring-version comparability.
- R18. The skill-gap report must rank recurring requirement categories and normalized requirements by distinct assessed applications, distinguishing must-have/core demand and recorded evidence levels.
- R19. The aging report must separate pre-interview unresolved cases from waiting after engagement, showing recorded application age and current-stage age with access to the corresponding records.
- R20. The opportunity report must describe captured salary, work-model and seniority distributions with missing-data coverage and inventory freshness visible.
- R21. Opportunity inventory must retain a visibly separate discovery-data scope rather than inherit application filters that cannot be meaningfully applied to unlinked postings.

**Sankey**

- R22. The full Sankey must show recorded application transitions for the selected application population, excluding draft-only preparation and transient ghosted steps while retaining unresolved waiting paths.
- R23. Sankey labels and a readable transition-count table must distinguish flows from current-status counts, with unresolved waiting interpreted per R9.

**Investigation and usability**

- R24. Every overview conclusion must link to its supporting report and a matching inspectable set of applications or postings without silently changing scope.
- R25. Targeting outcome comparisons must distinguish assessments recorded before an outcome from retrospective assessments, treating match scores as fit measures rather than interview probabilities.
- R26. Skill-gap interpretations must distinguish missing or partial CV evidence from demonstrated inability, keeping “unknown” separate from “none.”
- R27. Salary comparisons must keep incompatible currencies, pay periods and employment types separate, with missing comparability information identified.
- R28. Inventory reporting must show collection freshness and recorded discovery-run errors, avoiding source-to-application yield claims when current links are absent.
- R29. Each report must provide readable tabular evidence alongside its visualization and support keyboard navigation without relying on color alone.
- R30. Empty selections, unavailable fields and failed report loads must be distinguishable, allowing navigation to other reports and retry after a load failure.
- R31. Refreshing the workspace must recalculate reports from available local data rather than retain the dated values in the ideation artifact.

### Key Flows

- F1. Decide where to focus next.
  - **Trigger:** The user opens reporting.
  - **Steps:** Read the decision brief and scope; inspect a supported channel, targeting or skill-evidence pattern; open its report; inspect the matching records.
  - **Covers R1–R3, R6, R11–R14, R17–R18, R24.**

- F2. Compare a consistent application population.
  - **Trigger:** The user narrows the application filters.
  - **Steps:** Select a date range, profile or source; inspect the updated overview; move between cohorts, stages, targeting, aging and Sankey while retaining that context.
  - **Covers R5–R8, R15–R19, R22–R23.**

- F3. Inspect discovered opportunities.
  - **Trigger:** The user opens opportunity inventory.
  - **Steps:** Read the separate inventory scope and freshness; inspect comparable salary or work-model groups; inspect the underlying postings and available collection-error information; return to the retained application context.
  - **Covers R6, R20–R21, R24, R27–R28.**

- F4. Recover from sparse or unavailable data.
  - **Trigger:** A selection has no matching records, insufficient observations or a report-load failure.
  - **Steps:** Read the applicable state; inspect any available counts; adjust the selection, open another report or retry a failed load.
  - **Covers R11, R13, R29–R31.**

**Overview composition:** Shared application scope appears above the decision brief and summary metrics; a Sankey summary follows, with navigation to the full eight-view report set.
Detailed reports place the visualization, its qualified interpretation and inspectable evidence together.
Opportunity inventory visibly changes data scope per R21, while the application context is retained for return navigation.
This describes the selected sketch B structure; exact presentation belongs to implementation planning.

### Acceptance Examples

- AE1. Fresh applications do not become confirmed ghosting.
  - **Covers R9–R10, R19, R22–R23.**
  - **Given:** A newly activated application has recorded applied and automatic ghosted events.
  - **When:** It appears in aging or Sankey.
  - **Then:** It is described as unresolved with recorded age, not a confirmed terminal employer outcome.

- AE2. Recent cohorts are not penalized for missing observation time.
  - **Covers R15.**
  - **Given:** An application cohort is five recorded days old and has no interviews.
  - **When:** Its cohort row is displayed.
  - **Then:** Its 7-, 14- and 30-day outcome cells are unavailable rather than zero-percent completed windows.

- AE3. Unknown source remains unknown.
  - **Covers R7, R11–R14.**
  - **Given:** Source attribution is absent for most applications and recruiter-tagged entries have a higher observed interview incidence.
  - **When:** Channels are compared.
  - **Then:** Missing sources remain a separate group and the report does not equate them with cold applications or claim recruiter outreach caused the difference.

- AE4. Filters and supporting records agree.
  - **Covers R5–R6, R24.**
  - **Given:** The user selects an application date range and profile.
  - **When:** They follow an overview conclusion to its report and matching applications.
  - **Then:** The population and scope remain consistent, and returning to the overview preserves the selection.

- AE5. Assessment availability does not create fake low scores.
  - **Covers R11, R13, R17, R25.**
  - **Given:** Some applications have no assessment and one assessment was recorded after an interview.
  - **When:** Targeting is analyzed.
  - **Then:** Unassessed records do not enter a zero-score band and retrospective scoring is distinguished from pre-outcome evidence.

- AE6. Skill evidence is not an employer explanation.
  - **Covers R12, R18, R26.**
  - **Given:** Several requirements in one application share a technical category and evidence is partial, none or unknown.
  - **When:** Category demand is aggregated.
  - **Then:** That application is not counted repeatedly within the same displayed category/evidence group, and the report does not claim the gap caused rejection.

- AE7. Inventory is not the current market.
  - **Covers R20–R21, R27–R28.**
  - **Given:** Captured postings are stale, salary units vary, and current application links are absent.
  - **When:** The user opens inventory from a filtered application report.
  - **Then:** Collection dates and separate scope are visible, incompatible salaries are not pooled, and application-conversion yield is unavailable.

- AE8. Historical progression does not imply a completed pass rate.
  - **Covers R8, R11–R13, R16.**
  - **Given:** Some round-1 applications progressed and others remain active without a recorded outcome.
  - **When:** Stage progression is shown.
  - **Then:** The report separates observed progression from unresolved cases instead of classifying all non-progressed applications as failures.

- AE9. Reading reports leaves the search record unchanged.
  - **Covers R4, R30–R31.**
  - **Given:** The user opens reports, applies filters and refreshes, including an empty selection and a failed load.
  - **When:** They return to the existing application tools.
  - **Then:** Reporting interactions have not changed their tracked data or histories.

- AE10. Sankey preserves distinct preparation and outcome semantics.
  - **Covers R7–R9, R22–R23.**
  - **Given:** Records include a draft-only application, an applied-to-ghosted-to-interview history and an unresolved applied-to-ghosted history.
  - **When:** Sankey is generated.
  - **Then:** Draft-only preparation produces no application flow, transient ghosted is absent from the interview path, and unresolved waiting remains separately visible.

### Scope Boundaries

- Record editing, status updates, follow-up sending and discovery execution remain outside this read-only reporting feature, per R4.
- Offer forecasting, hiring-probability claims, causal CV-effectiveness analysis and inferred employer rejection reasons are excluded, per R12–R13 and R25.
- Peer benchmarking, new employer communication capture and new data collection integrations are deferred.
- Existing match assessments supply the skill and targeting inputs; generating or rescoring them is not required by this feature.
- Practice-readiness trends are not one of the seven selected reports and are deferred.
- The selected breadth is one reporting workspace; independent redesigns of the application manager, interview tools or discovery workflow are not included.

### Dependencies and Assumptions

- Existing local records are the reporting authority; no correction of their historical dates or reconstruction of deleted transitions is assumed.
- Report coverage grows as local records change, but missing data remains valid input rather than a reason to fabricate values.
- The user can run the existing local application server to view browser reporting.
- Cohort, targeting and channel results remain descriptive for this single-user dataset; a useful report need not produce a recommendation on every selection.

### Outstanding Questions

- Chart rendering, responsive presentation and navigation are resolved by KTD2 and KTD8.
- Deterministic label normalization is resolved by KTD4.
- Evidence sufficiency and insight ordering are resolved by KTD7.
- Launch and record inspection mechanics are resolved by KTD8.

### Sources and Research

- [Ranked reporting ideas and dated aggregate findings](../ideation/2026-10-23-application-reporting-ideation.html): the seven selected directions and their evidence limits.
- [Status transition semantics](../../cv_optimizer/tracker.py): lines 249–350 document automatic ghosted insertion, replacement and history removal on backtracking.
- [Existing Sankey cleanup](../../cv_optimizer/sankey.py): lines 12–82 distinguish preparation, transient ghosted and retained unresolved paths.
- [Match scoring and evidence definitions](../../cv_optimizer/matching.py): lines 1–12 and 39–72 distinguish candidate fit from tailored-document quality and define requirement evidence levels.
- [Product purpose and interface principles](../../PRODUCT.md): solo job-seeker, local workflow, dark-first precision and keyboard accessibility.

---

## Planning Contract

**Product Contract preservation:** Product Contract unchanged in scope and meaning; R1–R31, F1–F4 and AE1–AE10 retain their IDs. Its planning-owned questions now point to their technical resolutions.

### Assumptions

These are unconfirmed implementation defaults, not additional product commitments.

- Use the existing FastAPI server and a browser workspace at `/reports`; users keep the server running as assumed by the Product Contract. A new TUI command opens that URL rather than starting a server.
- Use server-generated report models with native HTML/SVG presentation. The dataset is small enough for one in-memory response containing all report models and their inspectable evidence; no pagination, cache service or database indexes are needed initially.
- Interpret timezone-free SQLite timestamps as UTC, matching SQLite's `CURRENT_TIMESTAMP` convention. This does not establish the timezone of manually backfilled values.
- Use calendar weeks starting Monday for cohorts and explicit conservative editorial thresholds for overview conclusions. These thresholds control wording, not statistical significance or report availability.

### Key Technical Decisions

- KTD1. **Separate read-only extraction from existing database helpers.** Governs R4, R6, R30–R31. Add `cv_optimizer/reporting/reader.py`, reading the configured `db.DB_PATH` value without calling database access helpers. Open an escaped file URI with `mode=ro`, enable connection-local `query_only`, and explicitly begin a deferred read transaction before the first schema/data read. Read required tables into memory from that transaction, capture one UTC `as_of`, then close the connection before aggregation or HTTP rendering. Do not call `init_db`, `_connect`, journal-mode changes, checkpoints, migrations, tracker operations or assessment/discovery generation. Do not use `immutable=1` or copy just the main database file: the live WAL must remain visible. SQLite may maintain WAL shared-memory bookkeeping; R4 protects logical records and history, not a byte-identical SHM file. Missing database, unreadable database and incompatible core schema are load failures, never automatic initialization. Missing optional discovery/assessment tables produce explicitly unavailable report sections. This boundary is required because `db.get_all_transitions`, `get_application` and other apparent readers call `init_db`, which performs schema and profile migrations.

- KTD2. **One snapshot bundle drives navigation, charts and drilldowns.** Governs R1–R6, R24, R30–R31. Add a static reporting shell at `GET /reports` and a synchronous `GET /api/reports/snapshot` handler for blocking SQLite work. A response carries `snapshot_id`, retrieval time, `as_of`, canonical scope, filter options, per-report availability, overview insights, report models and allowlisted record summaries. A snapshot ID is a response identity, not persisted state or a cache lookup. Each aggregate group carries its exact member IDs, numerator IDs where relevant, and report-local predicate key. Filtering fetches a replacement bundle and swaps it atomically; abort or ignore older responses. Navigation and evidence inspection use the accepted bundle without another database query. Explicit refresh requests a fresh bundle with caching disabled. No per-record endpoints that can drift from the aggregate, background jobs or cross-request snapshot store are needed. Failure retains navigation and retry, marks retained data stale, and never displays the failed selection as successfully applied.

- KTD3. **An application fact model owns chronology and denominators.** Governs R5–R11, R15–R16, R19, R22–R23. Build one fact per application, with ordered history, first recorded applied event, first recorded interview, current status, engagement flags and assessment provenance. Sort valid status timestamps ascending with history ID as the stable tie-breaker. Current status is the last valid event at or before `as_of`; retain malformed/future events as diagnostics rather than silently treating them as current. A record with any recorded applied event belongs to the default population, even if currently draft. Never-applied records remain a separately inspectable excluded count. Records with an applied event but no valid applied timestamp belong to the all-dates population with unknown age; an explicit date range excludes them and shows the exclusion count. Profile/source filters apply to this same population. Include missing/legacy profiles as unknown, never infer IT from absent schema or values.

  Date filters are inclusive UTC calendar dates converted to a half-open interval from start midnight to the midnight after the end date. Default is all dates, profiles and sources. Filter by first valid applied timestamp, not creation or later status dates; after selection, retain all available history through `as_of`, including outcomes after the filter end date. Use elapsed seconds divided by 86,400 for recorded-day horizons, with exact boundary events included. An interview before application is a chronology anomaly: retain its ever-interview flag for descriptive incidence, but exclude its interval from timed metrics and disclose the count. Unknown/future/negative ages are unavailable, not zero or silently clamped. Current-stage age starts at the beginning of the final consecutive run of the current status. Engagement means any recorded interview, offer or acceptance; it is not inferred from mock interview sessions.

- KTD4. **Conservative normalization preserves raw values.** Governs R11, R14, R17–R18. Add a versioned, code-owned mapping in `normalization.py`: Unicode NFKC, trim, collapse internal whitespace and casefold for all label keys. Blank values become explicit unknown buckets. Source aliases are exact matches: `recruiter`/`recruiter outreach` → recruiter, `referral`/`employee referral` → referral, `linkedin`/`linked in` → linkedin; other values retain their normalized key. Unknown never becomes cold application. Role-family aliases are exact: `frontend`, `front-end`, `frontend engineer`, `front end engineer` → frontend; corresponding backend forms → backend; `fullstack`, `full-stack`, `full stack`, `full stack engineer` → fullstack. Other labels remain separate normalized values, not guessed from application titles. Requirement text uses only the common text normalization, with no stemming, fuzzy matching or semantic extraction. Preserve punctuation, technology versions and original texts; category labels use the recorded matching taxonomy, with unsupported values marked unknown. Display all raw variants behind every merged label. This deliberately under-merges long requirement sentences rather than inventing equivalence.

- KTD5. **Assessment selection is descriptive first and timing-aware for comparisons.** Governs R17–R18, R25–R26. For descriptive fit/skill reporting choose the latest assessment at or before `as_of` by parsed creation time then assessment ID. Use its scalar score only when 0–100 and its JSON fields only when valid; count missing, invalid JSON and incomplete fields separately. Do not import matching generation machinery to parse historical JSON. Use score bands 0–39, 40–59, 60–79 and 80–100, explicitly labeled reporting bands rather than the matching product's named score labels.

  For outcome comparisons select the latest valid assessment strictly earlier than the first recorded interview, rejection, withdrawal, offer or acceptance after application. With no such event, select through `as_of` and label the observation unresolved. Equal timestamps across assessment/history tables do not prove precedence and are timing-unknown. Assessments only recorded after the outcome remain retrospective, with a separate descriptive table rather than entering pre-outcome rates. Interviews before application make timing eligibility unknown. Partition outcome comparisons by scoring version, prompt version, model and candidate hash; do not pool partitions or silently select the largest partition as the whole population. Show JD hash and assessment date in evidence. Role family comes from the assessment selected for that table, never a different/latest assessment. Skill reporting uses the descriptive selection and is labeled as an audit of assessed CV evidence, not necessarily evidence available before an outcome.

- KTD6. **Report definitions are shared computations, not chart-local arithmetic.** Governs R7–R23, R25–R28. The report-definition table below owns each report's aggregation. Every model supplies counts, denominator membership, coverage diagnostics and evidence IDs before visualization. An unavailable metric is null with a reason, never a zero. Unknown buckets stay in count tables even when excluded from comparison denominators. Chart labels come from these models, not independently recomputed JavaScript rates.

- KTD7. **A deterministic brief ranks investigation leads, not recommended allocations.** Governs R2, R11–R13, R24–R26. Generate templated conclusions only from accepted snapshot models; no LLM or external calls. Channel/targeting comparison leads require two known groups with at least 10 valid applications each, at least five interview events combined, a common fully observed 30-day window, and an absolute rate difference of at least 10 percentage points. Use 30-day interview attainment for these leads and name that horizon in the text; full reports still show all descriptive incidence. Targeting additionally requires a single comparable provenance partition and valid pre-outcome assessment timing for every member. Any candidate failing these checks stays descriptive with an insufficient-data reason; it is never described as a winning channel or a score cutoff.

  Comparison candidates use only applications with valid applied dates at least 30 recorded days before `as_of`, valid interview intervals and the selected shared scope. Each candidate's supporting report includes a separately labeled 30-day comparison table with precisely those denominator/numerator IDs; an insight opens that table rather than the all-history incidence table. This is an explicit analytical subset inside the retained scope, not an implicit filter change.

  A descriptive channel-concentration lead may say a known source accounts for X/Y recorded interviews when Y ≥ 5 and X ≥ 3, even if comparison thresholds fail. It must include source coverage and recruiter-selection bias and must not compare that source's success rate against unknown sources. A skill-evidence lead requires at least 10 valid assessed applications and at least five distinct applications in a must-have/core category with partial or none evidence; show partial and none separately and count their union once. Unknown evidence never enters that union. Rank eligible leads by kind (qualified comparison, descriptive concentration, recurring evidence inspection), then supporting distinct-application count descending, then stable report/group key ascending. Show at most three nonduplicate leads; keep all evidence in reports. If none qualify, show “insufficient data for a search-focus conclusion” with coverage and links. Aging does not become the main daily attention brief. Every lead carries its tested population, numerator, denominator, caveat and matching evidence selection.

- KTD8. **Native report navigation and read-only inspection.** Governs R1–R3, R20–R21, R24, R29–R30. Use one shell with hash routes for overview, channel, cohorts, stages, targeting, skills, aging, inventory and sankey. Store applied-date/profile/source parameters in the URL query, and report/group selection in the hash. The inventory view displays an independent “all captured postings” scope and retains the application query for return navigation. A selected evidence group opens an inline section with a heading, count and records table; moving focus to its heading makes keyboard navigation predictable. Application details show ID, company, role, source/profile, relevant dates, recorded history and assessment provenance/evidence. Posting details show captured compensation units, freshness and source references. Escape stored text, render descriptions as text rather than trusted markup, and allow only HTTP(S) external job links. No links to mutation-prone existing GET handlers such as `/api/open/{app_id}`, no local filesystem opening and no editing controls.

  Use responsive HTML tables, horizontal SVG bars, a semantic HTML cohort heatmap, and a native SVG Sankey without CDN dependencies. Sankey layout nodes are keyed by cleaned path position plus status, so unusual revisits cannot make the graphic cyclic. Aggregate links by these position-aware keys, with stable status/label ordering. Reuse a pure public chain-cleaning function extracted from `sankey.py`; existing `build_sankey_flows` uses the same cleaner without changing its public output. The reporting transition table retains ordinary status-pair occurrence counts and distinct application IDs. Give each chart a text summary and adjacent table; interactive selection lives in ordinary links/buttons rather than requiring SVG pointer interaction. At narrow widths the Sankey can scroll horizontally while evidence tables remain usable. Current-status totals are separate from flow counts; do not use the legacy renderer's edge-derived total as the application denominator.

- KTD9. **Keep the new evidence bundle same-origin on the loopback server.** Governs R4 and the local-workspace boundary in R1. The existing server's wildcard CORS middleware must not make the new career-history bundle readable by arbitrary websites. Add a reporting-path-only boundary that rejects explicit foreign browser origins and removes inherited wildcard CORS response headers for `/reports` and `/api/reports/snapshot`, including preflight and error responses. The browser uses same-origin requests; origin-free local clients remain usable. Keep the documented loopback bind and no new authentication system. Do not change CORS behavior for existing extension endpoints. Test through the actual middleware stack, not only direct handler invocation.

### Report Definitions

| Report | Population and computation | Visualization and evidence |
|---|---|---|
| Channel | Filtered applied applications, grouped by KTD4 source. Numerator is distinct ever-interviewed applications, denominator all group applications. Show known-source coverage and each group's recorded age distribution; rates are observed to date, not equal exposure. | Horizontal bars with X/N labels, unknown group, recorded-age table and recruiter-selection caveat. Group and interviewed-subset drilldowns. |
| Cohorts | First valid applied date grouped into Monday-start UTC weeks. For H=7,14,30 days, a cell is available only when every application in that selected cohort has had H days of follow-up by `as_of`. Numerator is first valid interview in [applied, applied+H]; denominator the full cohort. Show matured-member count even when the cell is unavailable. Unknown applied dates and interval anomalies are separate diagnostics. | Weekly volume and heatmap with X/N, explicit immature state and chronology exclusions. Cell evidence includes cohort membership, maturity and within-window interview flags. |
| Stage loss | For each actually recorded applied/interview-N/offer stage, count each application's first visit once. Partition visits into progressed to a later engagement stage, rejection, withdrawal, accepted, unresolved, or unknown/anomalous resolution using the first subsequent decisive event in chronological order. A jump from applied to interview 3 is progression from applied, not inferred visits to rounds 1/2. Ghosted is unresolved, not loss. | Stacked count bars and partition table; distinct stage-visit denominator. Rejection breakdown uses highest interview stage actually preceding rejection, with a separate no-prior-interview group. Progressed visits are historical and can coexist with later rejection in later rows, not within one row's partition. |
| Targeting | KTD5 descriptive/latest coverage plus pre-outcome comparison tables, grouped separately by score band and normalized assessed role family within each provenance partition. Outcome numerator is distinct ever-interviewed members. Show N, assessment/timing coverage and follow-up ages. | Horizontal incidence bars and tables for eligible, retrospective, timing-unknown and unassessed/invalid groups. Every group links to the selected assessment records. |
| Skill gaps | KTD5 latest descriptive assessment among filtered applied applications. Count distinct application IDs per category and per normalized requirement text, with separate must-have (`priority=must`), core (`is_core=true`) and their union. Count each evidence level separately; an application may appear in multiple evidence columns, so column totals need not sum to the row total. Rank by distinct must-have/core partial-or-none union descending, then distinct demand count, then normalized key. | Category/evidence matrix plus full normalized-requirement table, raw variants and evidence paths. State selected-assessment coverage and counts of malformed or missing requirements. Unknown and unsupported levels stay separate from none. |
| Aging | Filtered applied applications not currently rejected, withdrawn or accepted. Split no-ever-engagement and ever-engaged waiting. Offer is engaged waiting. Ghosted maps to no recorded outcome, with pre/post-engagement distinction. Current draft after applied stays visible in a separate returned-to-preparation group, not silently counted as employer silence. | Recorded application-age buckets 0–6,7–13,14–29,30+ days plus unknown; current-stage age and last status in inspectable records. Unknown current statuses are flagged rather than assigned a terminal meaning. |
| Inventory | All distinct captured posting IDs, independent of application filters. Work model/seniority show unknown and known coverage. Salary range entries are grouped by exact normalized currency, pay period and employment type; incomplete grouping keys are non-comparable. Do not annualize, convert currencies, midpoint-average open ranges or merge employment types. | Salary range SVG by comparable group, work-model/seniority bars, posting table and discovery-run status/error table. Show first/last seen, last completed collection time and elapsed freshness. Label data older than 30 days “older than 30 days,” not objectively inactive. Missing runs are unavailable, not proof of healthy collection. |
| Sankey | The selected applied population and its ordered recorded paths through `as_of`. Apply shared draft/transient-ghosted cleanup and consecutive deduplication. Retain terminal ghosted as no recorded outcome with previous engagement context. Single-stage applied records contribute to population/current-status totals even with no transition edge. | Overview summary and full position-aware SVG, status-pair transition-count table and separate current-status counts. Link counts are transition occurrences; show distinct contributing applications separately and never sum edges as total applications. |

### High-Level Technical Design

**Component and data-flow sketch:** Browser shell → snapshot GET → read-only reader → application facts → report models and insight selections → bundle → shared charts/tables/evidence. The pure Sankey cleaner feeds both legacy aggregation and the reporting Sankey model. Only the reader touches SQLite; only the browser owns navigation state.

**Snapshot protocol sketch:** Parse and validate scope → open one read transaction → inspect schema and extract rows → capture response identity/time and close connection → normalize facts → build each available report → derive brief → return bundle → atomically accept bundle. Optional-report failures carry local error states; core extraction failure returns a load error rather than a partial application population.

**Browser lifecycle sketch:** Initial shell → loading → accepted bundle; filter or refresh → loading with previous snapshot marked stale → accepted replacement or failed-load state with retry. Navigation and evidence selection remain within the accepted bundle. Back/forward restores URL scope, fetching a new bundle only when application filters differ. Group selections missing after refresh are cleared with a visible explanation, never silently remapped.

**API and validation sketch:** The snapshot accepts only start/end ISO dates, one stored profile key and one normalized source key, with empty meaning all. Reject malformed dates, reversed ranges and unsupported filter keys with a visible validation response. Known empty selections are successful empty results. Report/group keys are generated from structured model keys, not interpreted as SQL or arbitrary expressions. POST/PUT/PATCH/DELETE are not added to the reporting surface.

**Decision sketch:** Core data unreadable → whole snapshot failure; optional table absent → affected report unavailable; valid population empty → empty selection; observations present but KTD7 fails → descriptive report plus insufficient-data brief; qualifying lead → linked conclusion. These are distinct states in models and presentation.

### Repository Evidence and Behavior Trace

- `server.py` already mounts local static files and uses Jinja2 templates; it has no reporting entry point. Use its request/template conventions, but avoid its write-capable database access patterns.
- `cv_optimizer/db.py` owns application/profile columns, status IDs and assessment/discovery schemas. Its `_connect` changes journal mode; `init_db` performs DDL and profile backfill. Reading through its convenience functions violates the reporting boundary.
- `cv_optimizer/tracker.py:update_status` inserts applied/ghosted on activation, deletes ghosted before later outcomes and deletes transitions on backtrack. Reporting can explain surviving recorded chronology, not reconstruct removed events or true employer-response times.
- `cv_optimizer/sankey.py:build_sankey_flows` is pure over preordered transitions. Its HTML entry point fetches through initializing helpers, opens a temporary file and loads a CDN; reuse the pure cleanup, not the launcher or legacy counting labels.
- `cv_optimizer/matching.py` defines requirement fields and evidence levels. `framework_depth_gap`, `partial`, `none` and `unknown` are distinct values; preserve them. Fit scores are not tailored-CV quality or hiring probabilities.
- `tests/conftest.py:temp_db` creates isolated SQLite fixtures. Reporting tests may initialize fixtures during setup, then replace `init_db` and write helpers with failure sentinels before exercising readers/routes.
- `tests/test_profile_requests.py` supplies request-boundary and isolated JavaScript harness patterns. `tests/test_sankey.py` already characterizes draft/ghosted cleanup.
- `README.md` documents ad hoc dependencies with no requirements/pyproject manifest, local Uvicorn startup and pytest as the test runner. No exact installed framework version is claimed by this plan.
- The linked ideation's 178 applied applications, 14 interview observations and 90 stale captured postings are dated evidence, not expected runtime counts or golden test fixtures. No new live-data query is needed to implement the definitions.

The behavior trace is source-based: activation/status updates belong to tracker/database writers, Sankey consumes their surviving history, and the server's existing record handlers can initialize storage or open files. Missing/corrupt report data has no existing reporting recovery path; the new shell and bundle models provide it under R30. Deleted history and actual employer event times cannot be recovered from the inspected code.

### External Guidance and Alternatives

- SQLite's [URI documentation](https://www.sqlite.org/uri.html) establishes read-only mode and warns that immutable connections disable locking/change detection. Its [isolation documentation](https://www.sqlite.org/isolation.html) establishes why all extraction reads must share one transaction to include a consistent committed WAL snapshot. These determine KTD1 rather than relying on filesystem copying.
- FastAPI's [template documentation](https://fastapi.tiangolo.com/advanced/templates/) supports the existing request-aware Jinja2 pattern. Keep blocking extraction in a synchronous route and create/close SQLite connections inside that worker, rather than sharing connections across threads.
- A static exported document would lose the refresh/filter/drilldown coherence required here. Independently queried report pages would risk disagreements between conclusions and evidence during concurrent updates. A single accepted bundle meets R24 without a cache lifecycle.
- Native charts avoid a second chart dependency and keep tables authoritative. The existing Plotly CDN renderer is unsuitable for an offline workspace; a new client chart framework would add packaging work without improving the eight small report models. These reversible rendering choices do not require competing storage/interface prototypes or a bake-off.

### System-Wide Impact and Boundaries

Only new reporting endpoints, reporting-path CORS handling, reporting assets, the pure Sankey cleanup seam and an additive TUI launcher are active integration surfaces. Existing TUI/CLI Sankey behavior remains characterized by its tests.
The reporting bundle is also a machine-readable read interface for local tools; no new agent tool, LLM action or prompt context is required.
All existing mutation, scoring and discovery workflows retain ownership of their records.

Considered and not built: schema repair, persisted snapshots, automatic refresh polling, automatic retry loops, fuzzy requirement clustering, statistical significance claims and optimal-allocation calculators. The first would violate R4; the others have no requirement or demonstrated cost that justifies their added mechanism. A missing field or failed load remains visible and manually retryable.

### Sequencing and Deferred Implementation Details

U1 establishes snapshot/fact correctness; U2 and U3 add all analytical models; U4 binds interpretations to evidence; U5 adds HTTP/browser integration; U6 completes charts and keyboard flows; U7 adds launch/docs and integrated regression proof.
U2 and U3 may be developed independently after U1, but all seven reports and full Sankey are required before delivery.
Exact helper names, final SQL projections and pixel-level chart spacing are deferred implementation details. No product or launch-blocking question remains.

---

## Implementation Units

### U1. Read-only snapshot and canonical application facts

**Goal:** Establish one immutable in-memory view of available local data with consistent chronology and filters.

**Requirements:** R4–R11, R30–R31; F2, F4; AE1, AE3, AE9.

**Dependencies:** None.

**Files:** Create `cv_optimizer/reporting/__init__.py`, `cv_optimizer/reporting/reader.py`, `cv_optimizer/reporting/facts.py`, `cv_optimizer/reporting/normalization.py`, `tests/test_reporting_reader.py`, `tests/test_reporting_facts.py`.

**Approach:**
1. Implement KTD1 extraction and explicit required/optional schema capabilities with an injectable clock and database path.
2. Build KTD3 facts and KTD4 keys while retaining raw fields and diagnostic counts.
3. Apply one canonical application scope and expose exact IDs for all default/excluded/unknown populations.

**Patterns to follow:** Isolated SQLite fixtures in `tests/conftest.py`, schema ownership in `cv_optimizer/db.py`, timestamp/ID history ordering in `get_status_history_with_ids`.

**Execution note:** Establish read-only and WAL consistency integration proof before wiring any browser route.

**Test scenarios:**
1. Covers AE9. Initialize a fixture, disable `init_db` and writer helpers, then read/filter/refresh; schema and logical rows are unchanged and no writer sentinel fires.
2. Missing database yields a load error and does not create a file; absent optional tables yield unavailable capabilities without altering schema.
3. A writer commits new rows between two extraction SELECTs in WAL mode; the first bundle remains internally consistent and the next snapshot sees the commit.
4. Equal-timestamp applied/interview/rejected events use history ID ordering for current status and prior-stage attribution.
5. All-dates versus inclusive date bounds, unknown applied timestamps, unknown profile, duplicate applied events and currently-draft-but-ever-applied membership follow KTD3.
6. Case/whitespace aliases merge deterministically; unrelated role/requirement strings and versioned technology names remain separate with raw variants intact.
7. Malformed/future timestamps and pre-application interviews produce visible diagnostics and unavailable intervals rather than negative or fabricated ages.

**Verification:** Fixture populations and diagnostics match hand-calculated expectations; reads include committed WAL data without schema or record mutation.

### U2. Channel, cohorts, stages and aging models

**Goal:** Compute the four history-based reports from a shared selected population.

**Requirements:** R7–R16, R19, R29–R30; F2, F4; AE1–AE3, AE8.

**Dependencies:** U1.

**Files:** Create `cv_optimizer/reporting/application_reports.py`, `tests/test_reporting_application_reports.py`.

**Approach:** Build KTD6 models from facts, carrying group/numerator membership, coverage and availability reasons. Implement the four owning definitions in Report Definitions without chart-specific math.

**Patterns to follow:** Pure collection aggregation in `sankey.py`, ordered histories from U1.

**Test scenarios:**
1. Covers AE3. Known recruiter/referral and unknown sources retain distinct application denominators, numerators and coverage; duplicate histories cannot inflate incidence.
2. Covers AE2. A five-day cohort has null 7/14/30-day rates; exact H-day maturity and interview boundaries are included, while an event just after H is excluded.
3. A partially matured weekly cohort shows matured count but no full-cohort rate; a fully matured zero-interview cohort shows genuine 0/N.
4. Covers AE8. Applied/interview/skipped-stage/rejection/withdrawal/accepted/unresolved histories produce disjoint per-stage partitions and no invented intermediate visits.
5. Rejection before any interview, interview before rejection and tied timestamps with different IDs produce the correct rejection-stage group.
6. Covers AE1. Fresh default ghosted is unresolved; post-interview ghosted is engaged waiting; a returned draft is separate; repeated current-status entries use the final run's start for stage age.
7. Empty populations and missing/invalid stage dates distinguish empty counts from unavailable timing metrics.

**Verification:** Every displayed count reconciles to its evidence IDs and denominators, including unknown buckets and immature windows.

### U3. Targeting, skills and opportunity inventory models

**Goal:** Complete the assessment-based and independently scoped discovery reports.

**Requirements:** R11–R13, R17–R18, R20–R21, R25–R28; F3, F4; AE5–AE7.

**Dependencies:** U1.

**Files:** Create `cv_optimizer/reporting/assessment_reports.py`, `cv_optimizer/reporting/inventory_report.py`, `tests/test_reporting_assessment_reports.py`, `tests/test_reporting_inventory.py`.

**Approach:** Select assessments under KTD5, build the KTD6 targeting/skill/inventory models, and retain provenance and raw evidence for inspection. Validate historical JSON defensively without invoking matching or discovery code.

**Patterns to follow:** Recorded schema in `db.py`, evidence taxonomy in `matching.py`, synthetic job data in discovery tests.

**Test scenarios:**
1. Covers AE5. No assessment, before-outcome, tied-time, after-outcome and multiple-assessment cases select the correct evidence without creating zero-score assessments.
2. Score boundaries 0/39/40/59/60/79/80/100 map exactly; mixed versions/models/candidate hashes remain separate comparison partitions.
3. Covers AE6. Repeated requirements in one application count once per category/evidence cell and union; overlapping partial/none groups do not inflate union counts, and unknown is separate.
4. Malformed JSON, missing role family, unknown evidence/category and missing timestamps reduce explicit coverage without crashing other reports.
5. Covers AE7. Changing application filters leaves inventory membership unchanged; work-model/seniority missing values remain explicit.
6. USD/hour/contract and PLN/month/employment salary entries stay separate; open ranges and missing units do not become comparable averages.
7. Missing discovery tables are unavailable; stale sightings, running/failed runs, malformed errors and zero current application links remain descriptive and never produce conversion yield.

**Verification:** All assessment selections and salary comparability groups can be checked against their underlying fixture records; inventory has no application-filter dependency.

### U4. Snapshot-bound brief and Sankey evidence

**Goal:** Produce qualified focus leads and consistent overview/full Sankey models.

**Requirements:** R2–R3, R9, R11–R13, R22–R26; F1; AE4, AE10.

**Dependencies:** U2, U3.

**Files:** Modify `cv_optimizer/sankey.py`; create `cv_optimizer/reporting/insights.py`, `cv_optimizer/reporting/sankey_report.py`, `tests/test_reporting_insights.py`, `tests/test_reporting_sankey.py`; extend `tests/test_sankey.py` only as needed for the pure cleanup seam.

**Approach:**
1. Extract shared pure chain cleanup while retaining legacy aggregation output.
2. Build position-aware Sankey links and status-pair evidence under KTD8.
3. Implement KTD7 eligibility, wording, deduplication and ordering, adding its explicit 30-day comparison subsets to the supporting report models.

**Patterns to follow:** Existing pure Sankey tests and its preordered transition input contract.

**Test scenarios:**
1. Covers AE10. Draft-only, applied/ghosted/interview and unresolved applied/ghosted histories preserve cleanup and waiting semantics in both summary and full models.
2. Single-stage applied, duplicate consecutive statuses and nonconsecutive revisits retain the correct population, flow occurrences and distinct contributors without cyclic SVG layout keys.
3. Comparison thresholds just below/at 10 applications, five interviews, 30-day maturity and 10 percentage points choose the prescribed descriptive/qualified states.
4. Sparse recruiter observations permit only a qualified concentration description when its own counts qualify, never a causal winner or unknown-source comparison.
5. Skill leads count the partial/none union once; invalid provenance/timing suppresses targeting comparisons; no eligible candidates yields the explicit insufficient-data state.
6. Covers AE4. Every conclusion's evidence IDs match its exact accepted report population, including the labeled 30-day subset rather than all-history incidence; deterministic ties and input reordering do not change ranking.

**Verification:** Existing Sankey output remains compatible; every lead's wording and selection are reproducible from fixture report models without external calls.

### U5. Reporting routes and snapshot shell

**Goal:** Deliver the full analytical bundle through the existing local server with scope-safe browser state.

**Requirements:** R1, R4–R6, R21, R24, R30–R31; F1–F4; AE4, AE7, AE9.

**Dependencies:** U4.

**Files:** Modify `server.py`; create `cv_optimizer/reporting/service.py`, `templates/reports.html`, `static/reports.js`, `tests/test_reporting_routes.py`, `tests/test_reporting_browser_state.py`.

**Approach:** Add the KTD2 shell and bundle route, assemble optional report states independently, and implement URL scope/hash navigation under KTD8. Apply KTD9 to reporting paths through the actual middleware stack. Deliver escaped model data and allowlisted record summaries, not arbitrary database/file access.

**Patterns to follow:** Existing `Jinja2Templates` and static mount, FastAPI request tests, isolated Node script harness in `tests/test_profile_requests.py`. Use HTTP-level TestClient coverage for real routing/serialization, with `httpx` documented as a test dependency if needed.

**Test scenarios:**
1. HTTP GET renders the shell and a fixture-backed snapshot with all eight report keys, canonical scope and retrieval time; reporting requests never invoke writer sentinels.
2. Invalid/reversed dates and unsupported filter keys return validation states; a valid empty selection remains successful and empty.
3. Covers AE4. Filter → insight → report → evidence → back preserves scope and member IDs; a delayed old response cannot overwrite the latest accepted selection.
4. Covers AE7. Inventory displays independent scope while return navigation restores application filters.
5. Covers AE9. Missing database and injected optional-report failure preserve usable navigation, distinguish load failure from empty/unavailable data, and succeed after explicit retry.
6. Refresh recalculates using new fixture data; obsolete group selections are visibly cleared and no HTTP/browser cache serves a dated bundle.
7. Stored script-like labels, unsafe URL schemes and SQL-like filter values remain inert or rejected, with no shell/file opening or generation calls.
8. Same-origin and origin-free requests work; explicit foreign origins cannot read reporting responses or preflight through inherited wildcard CORS, while existing extension endpoints retain their CORS behavior.

**Verification:** The actual HTTP boundary, template serialization and browser-state transitions obey one bundle's identity and scope across F1–F4.

### U6. Charts, tables and accessible evidence inspection

**Goal:** Make the overview and every detailed report readable and navigable in the local browser.

**Requirements:** R1–R3, R6, R11–R13, R14–R24, R26–R30; F1–F4.

**Dependencies:** U5.

**Files:** Extend `templates/reports.html`, `static/reports.js`; create `static/reports.css`, `tests/test_reporting_presentation.py`.

**Approach:** Render KTD6 models using KTD8 native charts and evidence tables, following `PRODUCT.md` dark-first precision. Keep the search-focus brief above the Sankey summary, with all detailed reports reachable from navigation. Include explicit count/coverage labels, captions, keyboard focus and report-local failure/empty states.

**Patterns to follow:** Existing server template/assets organization and `PRODUCT.md` accessibility principles, without copying unsafe trusted-markup rendering.

**Test scenarios:**
1. Each report's model renders a captioned table and matching visible chart labels, including zero, unknown, insufficient and unavailable states.
2. Keyboard activation opens evidence and moves focus to its heading; returning retains report/filter context and does not require chart hover or color interpretation.
3. All eight detail routes render with fixtures; the overview has at most three qualified leads and a Sankey summary rather than a daily task queue.
4. Chart rendering failure leaves the tabular evidence visible; inventory's independent scope and stale-data labels remain visible at narrow width.

**Verification:** In a real browser, inspect desktop and 390px-wide layouts, tab through filters/nav/evidence/retry, verify readable focus and contrast, and disable network access to confirm no remote chart dependency. Compare representative chart labels against evidence counts rather than relying on screenshots alone.

### U7. Launch, documentation and end-to-end read-only proof

**Goal:** Make reporting discoverable from existing tools and prove the complete read-only journey.

**Requirements:** R1, R4, R24, R29–R31; F1–F4; AE1–AE10.

**Dependencies:** U6.

**Files:** Modify `cv_optimizer/tui/app.py`, `README.md`; create `tests/test_reporting_launch.py`, `tests/test_reporting_integration.py`.

**Approach:** Add an additive “Reports” command-palette action opening `http://localhost:8000/reports`, with an explicit server-running hint. Preserve existing Sankey shortcuts. Document direct launch, scope/time definitions, read-only limitations, refresh, offline assets and test dependencies. Exercise the full browser/API journey against a synthetic database with write sentinels after setup.

**Patterns to follow:** Existing `action_sankey` browser-launch convention and command-palette action registration in `cv_optimizer/tui/app.py`.

**Test scenarios:**
1. Reports palette action opens the reporting URL without database initialization, server spawning or modification of existing Sankey bindings.
2. Covers AE1–AE10. A deterministic synthetic dataset containing the acceptance-example histories, sparse/mixed assessments and stale mixed-unit postings reconciles overview, reports and evidence under all/profile/source/date scopes.
3. Capture logical database contents and schema after fixture setup, then open/filter/navigate/inspect/refresh, including failure and retry; the contents and schema remain unchanged.
4. A concurrent writer changes the fixture between refreshes; each accepted bundle remains internally coherent and the next refresh reflects the change.

**Verification:** Complete the Verification Contract and record the actual check outcomes. Browser evidence establishes F1–F4; database assertions establish R4 across the same integration boundary.

---

## Verification Contract

Commands below are implementation-stage checks; they were not executed during planning.
Use temporary synthetic SQLite fixtures, never the personal `applications.db`, for mutation/concurrency tests.
Set up fixtures before installing failure sentinels on initialization and writers.

| Gate | Command or check | Required outcome |
|---|---|---|
| Snapshot/facts | `python3 -m pytest tests/test_reporting_reader.py tests/test_reporting_facts.py -q` | U1 read-only, chronology, normalization and WAL snapshot cases pass. |
| Analytics | `python3 -m pytest tests/test_reporting_application_reports.py tests/test_reporting_assessment_reports.py tests/test_reporting_inventory.py -q` | U2/U3 numerators, membership, maturity, coverage and comparability reconcile. |
| Interpretation/Sankey | `python3 -m pytest tests/test_reporting_insights.py tests/test_reporting_sankey.py tests/test_sankey.py -q` | U4 thresholds and evidence selections pass; legacy Sankey behavior remains compatible. |
| HTTP/browser-state | `python3 -m pytest tests/test_reporting_routes.py tests/test_reporting_browser_state.py tests/test_reporting_presentation.py -q` | U5/U6 route serialization, race handling, error recovery and semantic presentation pass. Node-backed checks must actually run for shipping, not silently skip. |
| Integrated launch | `python3 -m pytest tests/test_reporting_launch.py tests/test_reporting_integration.py -q` | U7 launch and read-only acceptance journeys pass. |
| Repository regression | `python3 -m pytest tests/ -q` | Full suite passes or unrelated baseline failures are evidenced and reported without altering reserved user files. |
| Live browser | Existing local server startup: `uvicorn server:app --host localhost --port 8000`, then `/reports`; use an isolated fixture-backed server for R4 proof. | F1–F4, desktop/narrow layout, keyboard focus, refresh/retry, all eight details and exact evidence counts checked in a real browser. |

The repository documents no lint/typecheck/build or `release:validate` command, so none is invented here.
FastAPI HTTP tests need a compatible `httpx`; the isolated script harness needs Node. Document these test prerequisites without introducing a package-management migration.
No paid model calls, discovery runs or new assessments are needed for these checks.

---

## Definition of Done

- U1–U7 each meet their Verification outcomes and carry evidence for their enumerated scenarios.
- R1–R31 and F1–F4 are implemented; AE1–AE10 are enforced by the linked fixture tests and integrated journey.
- Overview, all seven reports and full Sankey work from fresh local records, including empty, unavailable, insufficient and failed-load states.
- Every conclusion reconciles with a supporting report and exact inspectable record set in one accepted snapshot.
- Read-only integration proof shows no schema, application, history, assessment or discovery-row changes from reporting interactions.
- Settled product choices remain intact, and no unsupported allocation, causality or employer-reason claims appear in interpretations.
- Browser checks demonstrate responsive presentation, keyboard access, usable non-color evidence and local chart assets.
- Verification results and any environment/baseline limitations are reported with the delivered change; unexecuted checks are not represented as passing.
- Documentation explains launch, date/denominator/cohort semantics, normalization, assessment timing, evidence thresholds and limitations.
- Abandoned experimental code/assets are removed from the final implementation diff, and unrelated user changes remain outside the feature's edits and staging.
