---
title: Responsive TUI - Plan
type: feat
date: 2026-10-22
topic: responsive-tui
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Responsive TUI - Plan

## Goal Capsule

- **Objective:** Let the job-seeker manage applications comfortably in split terminal panes and fullscreen, with available space improving readability and access to records.
- **Means:** Adaptive table-and-inspector and compact-record layouts, with continuous scrolling (KTD1–KTD3).
- **Product authority:** The confirmed responsive-TUI scope in this Product Contract; UI/UX redesign serving this outcome is permitted.
- **Open blockers:** None.
- **Execution boundary:** Implement U1–U5 and verify the contracts below; the invoking workflow owns subsequent shipping.
- **Stop condition:** Escalate evidence that any settled Product Contract choice is infeasible rather than weakening its requirements.

---

## Product Contract

### Summary

Build a responsive application dashboard with a table and selected-application inspector in wide panes and compact records in narrow panes.
Use continuous scrolling and adapt details, dialogs, navigation, and the funnel view to the available width and height.

### Problem Frame

The job-seeker's fullscreen example shows truncated company and role names beside unused horizontal space, with unused vertical space below the application list.
The same workflow must also work in tight terminal splits, where displaying every field and shortcut together competes with the records themselves.
Both dimensions matter: a short, wide pane and a tall, narrow pane have different constraints.

### Key Decisions

- **Combine the table-and-inspector and compact-record directions.** The user chose context on wide panes and readable records on narrow panes rather than one table layout everywhere. Governs R2, R3, R4. (session-settled: user-directed — chosen over a fluid table alone: combine the preferred wide-pane inspector with the preferred narrow-pane records.)
- **Use continuous scrolling.** Avoid page boundaries that shift when the pane is resized. Governs R5. (session-settled: user-approved — chosen over viewport-sized pages: use the available height without introducing resize-dependent pagination.)
- **Support tight splits as a real working size.** The user chose the smallest offered target rather than conventional terminal dimensions. Governs R1, R12. (session-settled: user-directed — chosen over 60 columns × 15 rows or 80 columns × 24 rows: support real work in very tight panes.)
- **Include related interaction surfaces.** A responsive dashboard is insufficient if its forms or actions cannot be used in the same pane. Governs R9, R10, R11. (session-settled: user-approved — chosen over a dashboard-only adjustment: retain usable workflows throughout the TUI.)

### Requirements

**Pane adaptation**

- R1. All existing TUI workflows must remain usable at terminal sizes of at least 40 columns × 12 rows.
- R2. Full-width panes must display the application table alongside an inspector for the selected application, leaving ordinary split panes list-only.
- R3. Narrow panes must display compact application records that expose company, role, status, and match score without horizontal scrolling.
- R4. When there is insufficient width or height for the inspector alongside the list, full application details must open separately without permanently reducing the list's working area.
- R5. The application list must use continuous scrolling through filtered results rather than fixed pages, with taller panes exposing more records when results are available.
- R6. Table columns must use surplus width to improve readability, prioritizing company and role over secondary metadata.

**Details and continuity**

- R7. Full application details must expose the complete company and role, status, match and readiness scores, CV profile, source, creation date, and document availability.
- R8. Resizing and layout changes must preserve the selected application, filter, and in-progress edits, keeping the selected record visible when the list is shown.

**Actions and secondary surfaces**

- R9. The footer must retain the original clickable key bindings for all available actions, with horizontal scrolling when they do not fit.
- R10. Existing actions must remain keyboard-accessible and operate on the selected application consistently across layouts.
- R11. Filtering, dialogs, and the funnel view must adapt to the pane, allowing scrolling or separate screens where needed to keep content and controls reachable.
- R12. Panes smaller than the R1 minimum may show a clear resize prompt while preserving the current application state.

**Height and content handling**

- R13. Short panes must reduce surrounding UI so the application list retains usable space.
- R14. Long content must remain readable through wrapping or scrolling in details and forms, with confirmation and cancellation controls reachable.
- R15. Layout changes must not cancel or duplicate background operations, and their progress or completion must remain accessible.
- R16. Roomy dialogs must retain the original centered 50-column layout, thick borders, spacing, and centered buttons while compacting to fit small panes.
- R17. Application lists must keep separate CV and CL availability indicators and date added visible, ahead of optional metadata.
- R18. The inspector and application-details modal must share readable formatting with prominent company/role, section headings, bold labels, and individual evidence/history entries while preserving complete literal values.

**Layout composition**

Per R2–R4, the wide layout places the application table on the left and the selected-application inspector on the right.
The narrow layout replaces the table with compact records and opens details separately.
Short panes prioritize the list over persistent details, with surrounding controls reduced per R13.
These describe region placement, not fixed breakpoint values or proportions.

### Key Flows

- F1. Browse and inspect applications.
  - **Steps:** Navigate the application list; the wide-pane inspector follows selection; open full details separately when space is limited; close details to return to the selected record.
  - **Covers R2, R3, R4, R5, R7, R10.**
- F2. Resize during work.
  - **Steps:** Select an application or begin editing; resize the terminal; continue from the same selection, filter, or edit when the layout adapts.
  - **Covers R8, R12, R15.**
- F3. Perform an action in a small pane.
  - **Steps:** Filter and select an application; invoke its action directly or through the action list; navigate the adapted dialog; confirm or cancel; return to the application list.
  - **Covers R1, R9, R10, R11, R14.**

### Acceptance Examples

- AE1. **Fullscreen uses available space. Covers R2, R5, R6.** Given enough applications to extend beyond the viewport, enlarging the pane reveals more records vertically and improves company and role readability horizontally, alongside the selected inspector.
- AE2. **A tight pane supports real work. Covers R1, R3, R4, R9, R10, R11, R14.** At 40 columns × 12 rows, the user can filter, navigate compact records, read complete selected-record details, and confirm or cancel an edit without inaccessible controls.
- AE3. **A short, wide pane remains usable. Covers R4, R13.** When height cannot accommodate persistent details and a usable list, details open separately and the list retains navigable rows.
- AE4. **Selection survives a layout switch. Covers R8.** After selecting an application deep in filtered results, narrowing and widening the pane preserves the filter and selected application without returning to the top.
- AE5. **Edits survive resizing. Covers R8, R11, R14.** Resizing with unsaved form values preserves those values and leaves save and cancel reachable.
- AE6. **Below-minimum sizes recover. Covers R8, R12.** Shrinking below 40 columns or 12 rows may show the resize prompt; enlarging again restores the current view and state.
- AE7. **Long records remain accessible. Covers R3, R7, R14.** A long company or role may be abbreviated in the list, but its complete value is readable in details and editable in the corresponding form.
- AE8. **Background work survives resizing. Covers R15.** Resizing during document generation or scoring does not restart the operation, and the user can still obtain its progress or completion result.
- AE9. **Empty results remain navigable. Covers R10, R11.** When a filter matches no applications, the user can change or clear it, and application-specific actions do not target a stale selection.

### Scope Boundaries

- The responsive pass includes the dashboard, inspector/detail views, filtering, action discovery, dialogs, and funnel view.
- UI/UX changes are permitted where they support the requirements above; existing application-management capabilities remain available.
- New job-management features, changes to CV generation or scoring behavior, and redesign of the web application are outside this work.
- Full working layouts below the R1 minimum are not required; R12 governs their fallback.

### Outstanding Questions

- **Deferred to Planning:** Exact width and height breakpoints, column allocation, compact-record wrapping limits, inspector proportions, and which shortcuts occupy the footer.
- **Deferred to Planning:** The rendering and data-loading approach for continuous scrolling and preserving selection during updates.
- **Deferred to Planning:** The verification approach for the supported terminal-size matrix, including live resize and long-content cases.

---

## Planning Contract

**Product Contract preservation:** User-directed refinement changes R2 and R9 and adds R16: reserve the inspector for full-width panes, restore the complete shortcut footer, and preserve the original modal appearance.

### Key Technical Decisions

- KTD1. **Use one mounted DataTable with two row presentations.** Desktop uses ordinary columns; compact mode uses one full-width, four-line Rich-text cell per application, without a column header. Both use application IDs as row keys. The fourth line preserves the R17 fields. This retains Textual's cursor, scrolling, and keyboard behavior without maintaining two competing selection models. Governs R2, R3, R4, R8, R17. (session-settled: user-directed — chosen over a fluid table alone: combine wide-pane context with readable narrow records.)
- KTD2. **Choose layout from width and height independently.** Use the layout policy below and screen classes changed by resize events, with measured content width controlling column allocation. Do not recompose the App or replace open forms on resize. Governs R1, R2, R4, R8, R12, R13. (session-settled: user-directed — chosen over 60 columns × 15 rows or 80 columns × 24 rows: support real work in tight splits.)
- KTD3. **Render every filtered result and let DataTable scroll.** Remove page size, page index, page slicing, and n/p pagination bindings. Keep native arrows, Home/End, and Page Up/Down as viewport navigation within one result set. Reuse the existing all-applications load, batching match and readiness lookups in chunks of at most 500 IDs per refresh. Cache these results by ID between refreshes; filtering does not reload application or score data. A new selection may fetch discovery detail under KTD5; resizing performs no SQLite queries. The chunk size avoids extending the existing SQL placeholder lists without bounding them. No data cap or lazy-loading protocol is needed for this solo desktop tracker. Governs R5, R8. (session-settled: user-approved — chosen over viewport-sized pages: avoid resize-dependent page boundaries.)
- KTD4. **Make selected application ID the action boundary.** Resolve actions through the current row key and the current filtered ID map, never page offsets or stale numerical coordinates. Before rebuilding rows, capture selected ID and visible anchor; restore the selection after layout, then scroll it into view. Refresh keeps the ID when present; deletion selects the next record at the old index, or the preceding final record. Filtering keeps the ID if it still matches, otherwise selects the first match; empty results clear selection and inspector. Ignore obsolete highlight events from a rebuild by checking their row key against the current table cursor and current results. Governs R8, R10.
- KTD5. **Share complete detail content between inspector and a separate detail screen.** Selection highlighting updates the inspector without Enter. Enter opens the full scrollable detail screen in every layout; Escape returns focus to the selected record. Keep R7 fields plus existing match breakdown, discovery metadata, URL, paths, and status history. Add explicit source and creation date, currently absent from the detail panel. Use cached match/readiness values; fetch discovery detail on the first selection of an ID and cache it until the next refresh. Refresh invalidates that cache and reloads the selected detail; resize uses cached content only. Treat company, role, URL, source, and paths as literal text rather than Rich markup. Governs R4, R7, R14.
- KTD6. **Restore the native interactive Footer and retain the action list.** Derive displayed hints from active bindings rather than maintaining a shortened static list; preserve native click dispatch and horizontal scrolling. The separate action list remains available through `?`, with discovery absent when disabled. Governs R9, R10, R11. (session-settled: user-directed — chosen over the shortened static footer: key shortcuts must remain visible and usable.)
- KTD7. **Keep modal instances alive and make their content scroll.** Use one shared sizing treatment for existing modal containers: pane-bounded width/height, no minimum wider than the pane, scrollable body, and a separate reachable action row. At short heights remove decorative padding, shorten titles, and use compact buttons; horizontal action groups stack if their measured widths cannot fit. Select menus must scroll within the pane. Escape cancels Status, Confirm, Edit, and Profile with no mutation; Source Escape retains the current source, preserving its existing distinction between clearing and cancelling. Filter focus is explicit: `/` reveals/focuses the mounted filter, Enter returns to the list, and Escape returns without clearing its text; clearing is an explicit action. Governs R8, R11, R14.
- KTD8. **Preserve Shift+S for the browser Sankey.** Keep the existing interactive HTML chart on its original shortcut; offer the compact terminal funnel separately as `Terminal funnel` in the action list. Reuse the existing rendering and counting semantics without changing aggregation. Governs R10, R11.
- KTD9. **Keep workers and notifications owned by the App.** Resize changes presentation only, never invokes refresh or worker launch, and never changes worker groups or exclusivity. Store the current operation message and most recent completion/error independently of result counts so list renders cannot erase them. Show a compact status line and provide the complete message in a scrollable status view through the action list. Completion refresh updates backing rows and inspector even while a modal is open, without stealing focus, changing its captured target, or resetting its inputs. Existing worker callbacks must not force selection to a completed application's ID if the user has since navigated elsewhere. Governs R8, R15.

### Layout Policy

Terminal dimensions are columns × rows. These are initial implementation defaults with explicit boundary coverage, not new product minimums.

| Condition | List | Inspector | Surrounding UI | Detail behavior |
|---|---|---|---|---|
| Width <40 or height <12 | Retain hidden mounted content | Hidden | Non-interactive resize overlay | Existing screen stack retained underneath |
| Width 40–79, height 12–17 | Compact records | Hidden | No Header; filter shown only while focused; one-line status and footer | Separate screen |
| Width 40–79, height ≥18 | Compact records | Hidden | Header, filter, status, footer | Separate screen |
| Width ≥80, height 12–17 | Desktop table | Hidden | Short-height treatment | Separate screen |
| Width 80–179, height ≥18 | Desktop table | Hidden | Normal controls | Separate screen |
| Width ≥180, height ≥18 | Desktop table | Right-hand inspector | Normal controls | Separate full detail also available |

In wide mode the inspector's outer width is 32% of the body, clamped to 36–52 columns, with one column between regions.
The remaining list width is measured after borders and scrollbar reservation, rather than inferred from terminal width.
At 40×12, compact mode reserves one status line and one footer line, leaving ten list lines when the filter is hidden and seven while its three-line Input is visible.
Four lines per compact record leave two complete records with the filter hidden and one complete record while filtering.
The below-minimum overlay applies over the active screen, including a modal, and blocks mutation shortcuts while allowing resize recovery and quit.
It must not push/pop screens or dismiss edits.

Desktop columns always include company, role, status, match, Added, CV, and CL per R17.
Allocate their content minima as 12, 18, 10, 5, 10, 3, and 3 cells, plus actual cell padding and a vertical scrollbar allowance.
Give remaining cells to company and role in a 2:3 ratio until their content fits, then admit secondary columns in order: readiness, source, JD, ordinal.
Admit a secondary column only after company has 24 and role has 36 content cells available; preserve these floors as metadata is added.
Use full original strings and terminal-cell-aware cropping in renderers rather than `_truncate` character counts.
Compact records place company on line one, role on line two, status plus match on line three, and labelled CV/CL indicators and Added date on line four; ellipsize only the two identity lines to the measured cell width.
Details own complete values under R7 and R14.

### High-Level Technical Design

**Component relationships.** CvDashboard owns result data, selection, operation state, and the screen stack. The list emits a row key to CvDashboard, which updates the shared detail content used by the inspector and detail screen. The action-list screen returns an action to CvDashboard. Existing modals return their existing result types to existing callbacks; workers report back through App callbacks. None of these child views owns database mutations or worker lifecycle.

**Data-flow sketch.** Refresh request → existing application query → chunked score/readiness queries → ID-keyed cache → current filter → keyed row presentation → restored cursor and inspector. Resize enters only at row presentation. Filter changes enter at current filter. Worker completion enters at refresh without replacing the modal stack.

**Layout-state sketch.** Evaluate undersize first; otherwise evaluate compact versus desktop by width, short versus normal controls by height, and inspector eligibility by both dimensions using KTD2. Every supported mode can transition to any other through a resize, retaining KTD4 state. Leaving undersize restores the underlying active screen, then reflows it at the recovered size. Opening detail or editing adds a screen state orthogonal to dashboard layout, rather than another dashboard mode.

**Resize lifecycle sketch.** Capture ID, focus owner, and visible anchor → update sizing classes and row presentation only if required → await completed layout → restore cursor visibility and focus. An open modal updates only its own geometry. Ignore redundant resize events and presentation-generated selection messages while restoring. A resize never enters the data-loading or worker-launch stages.

### Assumptions

- **Unvalidated agent bet:** The initial breakpoints and inspector ratio in KTD2 fit this user's terminal use. They are cheap to tune from the verification matrix while preserving R1–R15.
- **Unvalidated agent bet:** Loading all records remains appropriate for a solo tracker because the current application already loads all application histories. Check 1,000 synthetic records during implementation before considering a more complex loading mechanism.
- **Unvalidated agent bet:** Enter opening complete details even in wide mode is preferable to toggling the existing five-line panel. It preserves a keyboard path to content longer than the inspector viewport.

### Grounding and Behavior Trace

- `cv_optimizer/tui/app.py`: `refresh_apps` loads all applications but resets the page without an explicit ID; `render_table` slices twenty records and truncates identity strings. `_selected_app` applies page offsets. This is the behavior U1 replaces, not a database pagination constraint.
- `cv_optimizer/db.py`: `list_applications_with_status` already loads histories per application. `get_latest_matches` and `get_latest_readiness_batch` accept ID lists and return ID-keyed dictionaries, but construct one SQL placeholder per ID. KTD3 reuses these functions with bounded chunks; it does not claim the overall loader is free of N+1 queries.
- `cv_optimizer/tui/app.py`: status, source, profile, and edit callbacks refresh with explicit selection IDs. Generation callbacks also render/refresh with a target ID, while scoring/discovery callbacks refresh without one. U1/U5 must reconcile both paths under KTD4/KTD9.
- `cv_optimizer/tui/screens/modals.py`: forms are composed once and return values through dismissal callbacks. Profile has a width cap, while other modal CSS has fixed 50-column widths, generous padding, and no body/action separation. Reflow can preserve live Input/Select instances.
- `cv_optimizer/tui/app.py`: the detail panel updates on Enter, not highlight, and profile callbacks directly query it. Replace those direct panel refreshes with the shared detail update so separate details cannot become stale.
- `cv_optimizer/tui/screens/modals.py` and `cv_optimizer/sankey.py`: terminal SankeyScreen exists, but active `action_sankey` invokes `generate_sankey_html`. Terminal text is fixed-width and needs presentation adaptation; flow aggregation already exists.
- `tests/test_tui_pagination.py` protects action targeting, cursor continuity, and filtering. `tests/test_tui_profiles.py` also assumes pages and `#detail-panel`; migrate those assumptions while preserving its profile-selection, cancellation, invalidation, and file-retention assertions.
- `PRODUCT.md` requires dark, focused, precise terminal-first presentation. Use restrained borders, status colors, visible textual labels, and no decorative motion or card styling.
- `README.md` documents Python 3.12 and Textual 8.2 as tested versions, but explicitly has no dependency manifest or pin. This is a documented baseline, not proof of the installed version. Verify API compatibility at implementation start without bundling a framework upgrade.

Official Textual references were consulted through Context7 and the DataTable reference:

- [DataTable](https://textual.textualize.io/widgets/data_table/): stable row keys, Rich cells, explicit column widths, row heights, cursor navigation, and highlight/selection messages ground KTD1/KTD4. Explicit row heights avoid assuming that arbitrary wrapped cells automatically change record geometry.
- [Testing](https://textual.textualize.io/guide/testing/) and [Pilot](https://textual.textualize.io/api/pilot/): sized headless sessions and in-session resize drive the verification matrix.
- [Layout](https://textual.textualize.io/guide/layout/), [maximum height](https://textual.textualize.io/styles/max_height/), and [screens](https://textual.textualize.io/guide/screens/): bounded, mounted containers ground KTD2/KTD7.
- [Command palette](https://textual.textualize.io/guide/command_palette/): custom providers are possible, but KTD6 chooses the existing ModalScreen/callback pattern for tight-pane control.

### Risks, Boundaries, and Deferred Details

- The 40×12 target is feasible through scrolling and full-pane screens; it cannot show every control simultaneously. Verify actual focus traversal and Select overlays, not merely container dimensions. This is a constraint on implementation quality, not invalidating evidence against R1.
- DataTable is efficiently rendered but holding every row is not a claim of unlimited-scale virtualization. New viewport loaders, asynchronous database orchestration, and schema/query redesign are considered and not built: the current dataset is already loaded in full, and no measured loading bottleneck is available. A demonstrable stall on the synthetic workload would justify revisiting this decision.
- No worker regrouping, retry framework, or generation/scoring behavior change is planned. Fix only presentation coupling needed by R15; retain existing domain entry points and exclusivity semantics.
- Framework compatibility, final helper names, and cell-padding arithmetic are implementation-time checks. They do not reopen the product choices. If the documented public APIs differ in the installed version, adapt to its public equivalents and record that evidence.
- Database schema, web UI, CV prompts, extension UI, and scoring policy remain outside this implementation. Preserve current unrelated changes, including `.gitignore`, `cv_optimizer/prompts/optimize.md`, `extension/popup.html`, `tests/test_profile_prompts.py`, and `.compound-engineering/`.

---

## Implementation Units

### U1. Replace page state with continuous keyed browsing

**Goal:** Browse the complete filtered result set with reliable selection and action targeting.

**Requirements:** R5, R8, R10; F1, F2; AE1, AE4, AE9; KTD3, KTD4.

**Dependencies:** None.

**Files:** Modify `cv_optimizer/tui/app.py`, `tests/test_tui_pagination.py`, and `tests/test_tui_profiles.py`; add `tests/test_tui_scrolling.py`.

**Approach:**
1. Replace page arithmetic with keyed rows, cached score/readiness dictionaries, and explicit selected-ID restoration.
2. Separate data refresh from filtered/presentation render, retaining existing callback entry points until their callers are migrated.
3. Remove pagination controls and replace page-count status with selected position and result count, without owning operation messages.
4. Migrate legacy page-based tests to navigate beyond the twentieth row and assert application identity rather than a page number.

**Patterns to follow:** Existing isolated SQLite/Pilot tests and database batch lookups.

**Execution note:** Preserve the existing wrong-record and profile regression coverage before changing selection behavior.

**Test scenarios:**
1. Covers AE1. With 75 results, navigate through record 21 to the final record without invoking a page action; the selected ID matches the row key.
2. Covers AE4. Select record 57 in filtered results, refresh after a status/source/profile change, and retain its ID and active filter.
3. Covers AE9. Filter to no matches, invoke an application action, and observe no mutation or stale inspector; clearing restores navigable results.
4. Delete a selected middle record and then a final record; select the defined neighboring ID, with no selection after deleting the only result.
5. With 1,001 synthetic IDs, batch helpers receive no more than 500 IDs per call and scores align to IDs; filtering/re-rendering does not reload application or score data. A new selection may load discovery detail once under KTD5; repeated selection and resize use its cache.
6. Simulate a failed refresh and retain the previous usable result set while exposing the error, rather than partially replacing rows and selection.

**Verification:** No page-dependent action paths remain, every filtered record is reachable, and migrated profile tests retain their original domain assertions.

### U2. Implement adaptive list, inspector, and full details

**Goal:** Make width and height improve browsing while maintaining detail access in every supported pane.

**Requirements:** R1–R8, R12, R13, R14; F1, F2; AE1–AE4, AE6, AE7; KTD1, KTD2, KTD4, KTD5.

**Dependencies:** U1.

**Files:** Modify `cv_optimizer/tui/app.py`, `cv_optimizer/tui/dashboard.tcss`, `cv_optimizer/tui/screens/modals.py`, and `tests/test_tui_profiles.py`; add `cv_optimizer/tui/layout.py`, `tests/test_tui_layout.py`, and `tests/test_tui_responsive.py`.

**Approach:**
1. Put the pure size/column-budget policy in `layout.py`; keep screen orchestration in CvDashboard.
2. Introduce the horizontal body and inspector, and rebuild only row presentation when its column schema changes.
3. Share literal-text detail rendering between inspector and a scrollable detail screen, replacing direct profile callbacks into the old detail panel.
4. Add resize handling and a non-destructive below-minimum overlay under KTD2/KTD4.

**Patterns to follow:** Textual keyed DataTable rows and existing ModalScreen dismissal callbacks.

**Test scenarios:**
1. Covers AE1. At 200×50 with 75 records, more than 20 desktop rows are visible and long company/role values use surplus width beside the inspector.
2. Covers AE2 / AE7. At 40×12, each compact record shows all four required fields without horizontal scrolling; Enter exposes complete long names and all R7 fields.
3. Covers AE3. At 160×12 the inspector is absent and the desktop list remains navigable; Enter opens separate details.
4. Covers AE4. Select record 57, resize 160×50 → 40×12 → 80×24 → 160×50 in one session, and retain filter, selected ID, visible selection, and list focus.
5. Covers AE6. Resize through 39×12 and 40×11 then recover; retain screen stack and state, and prevent underlying mutation actions while undersize.
6. Move highlight rapidly between records and refresh during a layout switch; inspector content and action target match the final cursor rather than queued obsolete events.
7. Render company/role containing brackets, combining characters, wide CJK characters, and a long unbroken URL; keep literal content and measured column bounds correct.

**Verification:** Layout boundaries pass pure policy tests and live-session Pilot checks; selected details remain complete and consistent with the list.

### U3. Make action discovery and filtering usable in tight panes

**Goal:** Expose every existing capability without filling the working area with shortcuts.

**Requirements:** R1, R9, R10, R11, R13; F3; AE2, AE9; KTD6, KTD7.

**Dependencies:** U2.

**Files:** Modify `cv_optimizer/tui/app.py`, `cv_optimizer/tui/dashboard.tcss`, and `cv_optimizer/tui/screens/modals.py`; add `tests/test_tui_actions.py`; update `tests/test_discovery_flag.py` where action discovery is asserted.

**Approach:**
1. Add the pane-bounded action-list screen and footer visibility policy without duplicating domain handlers.
2. Route its selection back to the existing dashboard action methods and suppress selection-dependent actions when no record exists.
3. Keep the filter mounted through short-height visibility changes and enforce focus-local handling of typing, Enter, Escape, and question mark.

**Patterns to follow:** Existing Binding actions, discovery feature flag, and modal callbacks.

**Test scenarios:**
1. Covers AE2. At 40×12 the three primary hints fit; open Actions, scroll to its last command, dismiss, and return to the same application.
2. Invoke Edit and Status via both shortcuts and action discovery after scrolling beyond record 20; both paths capture the same ID.
3. Covers AE9. With empty results, global refresh/filter/funnel/quit remain available and selected-record commands cannot target an old ID.
4. Type `q`, `s`, `e`, `/`, and `?` into the filter and edit fields; they edit text without firing dashboard actions. Enter and Escape return from the filter without losing its text.
5. With discovery disabled its command is absent; when enabled it is available through the list and existing shortcut with existing behavior.

**Verification:** The action list covers every non-pagination binding, including browser Sankey and complete operation status, and no hidden footer binding becomes inaccessible.

### U4. Adapt dialogs and terminal funnel

**Goal:** Complete existing editing and funnel workflows inside the minimum working pane.

**Requirements:** R1, R8, R10, R11, R14; F2, F3; AE2, AE5, AE7; KTD7, KTD8.

**Dependencies:** U2, U3.

**Files:** Modify `cv_optimizer/tui/screens/modals.py`, `cv_optimizer/tui/dashboard.tcss`, `cv_optimizer/tui/app.py`, `tests/test_tui_profiles.py`, and `README.md`; add `tests/test_tui_modals.py` and `tests/test_tui_funnel.py`.

**Approach:**
1. Apply the shared scroll-body/action-row treatment to Profile, Status, Confirm, Source, and Edit while preserving their return values and validation behavior.
2. Keep focus, text, and Select state in the same mounted widgets as dimensions change, including nested profile-change confirmations.
3. Retain the browser chart on `S` and expose SankeyScreen in the action list; render terminal transition content from existing flow/count functions in a width-adaptive scrollable presentation.
4. Update README's TUI controls and supported-size guidance to match KTD6/KTD8.

**Patterns to follow:** Existing profile warning/invalidation tests and `build_sankey_flows`/terminal counting semantics.

**Test scenarios:**
1. Covers AE2 / AE5. At 40×12, use only the keyboard to reach every Edit field and Save/Cancel; resize with unsaved long values and save exactly those values to the captured application.
2. Covers AE7. A very long confirmation message can be read fully by scrolling, with Yes/No still reachable and no change on cancellation.
3. Open each Select at 40×12, reach the final status/profile option, then confirm or cancel without an off-pane overlay or button.
4. Resize a nested profile-change confirmation; cancellation retains the original profile/files, and acceptance retains the established invalidation/file-retention behavior.
5. Source Clear removes the override, while Cancel and Escape preserve it; other modal Escape paths perform no mutation.
6. Open the funnel with no transitions and with many transitions at 40×12; all labels/counts are readable, scrolling and Escape work, and list selection is restored. The browser chart action still invokes its existing entry point once.

**Verification:** Every existing modal completes and cancels by keyboard at 40×12; funnel rendering changes no aggregation semantics.

### U5. Verify resize continuity and background operation feedback

**Goal:** Prove the complete workflow across layouts, including operations that finish behind an open form.

**Requirements:** R8, R12, R15; F1–F3; AE1–AE9; KTD4, KTD9.

**Dependencies:** U1–U4.

**Files:** Modify `cv_optimizer/tui/app.py`, `tests/test_tui_responsive.py`, and `tests/test_tui_actions.py`; add `tests/test_tui_workers.py`.

**Approach:**
1. Separate operation messages from result-count rendering and expose the complete message through the action list.
2. Migrate worker render/refresh callbacks to preserve current user selection instead of selecting the operation's target.
3. Exercise the complete supported-size matrix using seeded records and controllable fake worker services.

**Patterns to follow:** Existing App-owned workers and call-from-thread UI updates; pytest temporary database fixtures.

**Test scenarios:**
1. Covers AE8. Hold a fake generation operation pending, resize through every layout and below minimum, then release it; exactly one service invocation finishes and progress/completion is readable.
2. Covers AE5 / AE8. Edit application B while generation for A completes; B's values, captured target, focus, and filter remain intact, and A's document indicator updates behind the form.
3. Finish fake scoring and discovery while viewing full details, then return to the list; selection and refreshed data remain consistent and the operation is not relaunched.
4. Report a long fake worker error, resize, then refresh; the complete error remains reachable through the status action rather than being replaced by the result count.
5. Covers AE1–AE9. Run the keyboard journeys in the Verification Contract, checking visible regions and mutation results rather than class names alone.

**Verification:** Responsive transitions do not launch, cancel, duplicate, or retarget background work; operation results remain available after list refreshes.

---

## Verification Contract

Use `tests/conftest.py` temporary SQLite and application-directory fixtures; synthetic records only, with network, browser launches, filesystem opening, and generation/scoring/discovery services replaced by controlled fakes.
No real LLM requests or user database access are required.
Record the installed Textual version when executing verification because `README.md` provides a tested baseline without a dependency pin.

The repository's documented test entry point is `python3 -m pytest tests/ -q`.
First verify the TUI suites named in U1–U5 and the existing profile/discovery-flag regressions; then use that full-suite entry point to detect shared integration regressions.
There is no release-validator or behavioral skill-evaluation configuration established for this UI change.

| Size or transition | Main proof | Required observation |
|---|---|---|
| 40×12 | Compact minimum, all modal types, filter, action list, details, funnel | Keyboard reaches complete content and every confirm/cancel control; no required horizontal scroll |
| 60×15 and 79×24 | Tight split and compact boundary | Readable records, filter continuity, complete details |
| 80×24, 160×24, and 179×24 | Desktop without inspector | Columns fit actual list region; separate detail accessible |
| 180×18 and 200×50 | Inspector boundary and fullscreen | Highlight follows selection; more height exposes more records and width improves identity text |
| 160×12 and 120×17 | Short/wide and height boundary | Inspector absent; usable list retained |
| 39×12, 40×11, then 40×12 | Below-minimum recovery | Overlay blocks underlying actions and restores live state |
| 160×50 → 40×12 → 80×24 → 160×50 | Live resize in one Pilot session | Deep selection, filter, focus, and unsaved modal input survive |

Pure policy tests cover both sides of 40/80/180 columns and 12/18 rows, including combined boundary conditions.
Headless Textual tests must inspect widget regions, scroll positions, selected row keys, focus, screen stack, and database effects after layout settles.
Counting rows in the model alone does not prove that more rows are visible.
Use live-session terminal resize through Pilot's public resize facility after checking the installed version's API; launching separate sessions at different sizes is not resize-continuity proof.

Perform a manual terminal pass at 40×12, 160×12, and fullscreen with long names, wide Unicode, absent scores/documents, empty results, and enough records to scroll beyond the old limit.
Capture visual evidence that primary hints and controls are legible and that the selected row is visible after transitions.
Exercise F1–F3 and AE1–AE9, including a fake operation finishing while a form is open.
Use 1,000 synthetic applications for a responsiveness smoke check: navigation and resize must remain usable, and resizing must cause zero database reloads and zero service starts.
If that workload visibly stalls, investigate the measured bottleneck before introducing a new data-loading architecture.

---

## Definition of Done

- R1–R18 are implemented with the revised Product Contract and stable IDs intact.
- U1–U5 meet their verification outcomes; F1–F3 and AE1–AE9 have behavioral evidence across the supported matrix.
- No page-state code or tests requiring fixed pages remain; previous wrong-record/profile regressions remain covered under continuous scrolling.
- Every non-pagination action is keyboard-accessible, dialogs preserve live edits, and all R7 details remain readable at the minimum size.
- Both terminal funnel and existing browser chart access work without changing funnel calculations.
- Background operations keep their existing domain semantics and survive presentation changes with accessible progress, completion, and errors.
- Documentation matches the controls, initial breakpoints, and minimum supported pane.
- Relevant targeted checks and the documented full suite pass, or any environmental limitation is explicitly reported with its affected proof.
- Remove abandoned experimental UI paths, obsolete panel/page logic, and unused imports introduced or made redundant by this work.
- The final diff preserves unrelated user edits and contains no generated documents or live application data from verification.
