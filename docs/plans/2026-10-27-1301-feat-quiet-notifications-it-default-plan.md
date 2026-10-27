---
title: Quiet Notifications and IT Default - Plan
type: feat
date: 2026-10-27
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# Quiet Notifications and IT Default - Plan

## Goal Capsule

- **Objective:** Let the job-seeker work without external notification interruptions and submit IT applications without repeatedly selecting their usual profile.
- **Means:** An opt-in notification setting and an IT popup default (KTD1, KTD2).
- **Authority:** Requirements govern behavior; technical decisions govern mechanism; units implement both.
- **Execution:** Local implementation and verification, followed by independent review and PR publication through the authorized LFG run.
- **Stop conditions:** A settled decision proves infeasible or a material repository prerequisite is missing.

## Product Contract

### Summary

Make Discord and desktop notifications opt-in together, and preselect IT in the extension popup.

### Problem Frame

The job-seeker wants fewer notification interruptions and mostly applies to IT roles, making repeated profile selection unnecessary.

### Requirements

**Notifications**

- R1. A global feature flag disables Discord and desktop notifications by default, even with a configured webhook.
- R2. Enabling the flag restores existing notification delivery; Discord additionally requires a webhook.
- R3. The flag covers success and failure notifications for applications and documents, plus discovery summaries, independently of TUI modal state.
- R4. Disabling external delivery must not prevent generation, discovery, logging, or in-app feedback.

**Extension**

- R5. Every newly opened extension popup preselects IT for both extraction and manual entry.
- R6. The user can still select Mechanical Engineering or Baker before submitting.

### Key Decisions

- **Global opt-in rather than modal-scoped suppression.** Governs R1–R3. (session-settled: user-directed — chosen over a TUI toggle or temporary modal pause: the user selected a global flag off by default.)
- **Desktop and Discord share the switch.** Governs R1–R4. (session-settled: user-approved — chosen over leaving desktop notifications enabled: the user corrected the scope to silence desktop notifications too and confirmed the combined flag.)

### Scope Boundaries

No modal redesign, remembered profile preference, notification queue, or separate per-channel controls. Preserve existing local modal-focus changes outside this work.

## Planning Contract

### Key Technical Decisions

- KTD1. Add `ENABLE_NOTIFICATIONS` / `settings.enable_notifications` using the existing `_env_flag` pattern in `cv_optimizer/config.py`. Gate delivery at server and discovery notification boundaries, including direct desktop failure paths. This implements R1–R4 without changing producers' outcomes. (session-settled: user-approved — chosen over leaving desktop notifications enabled: the user confirmed a shared opt-in switch.)
- KTD2. Change the selected option in `extension/popup.html` to IT; retain the existing selector and payload handling in `extension/popup.js` for R5–R6. No storage or API default changes are needed.

### Assumptions

The flag is read at process startup, matching `ENABLE_DISCOVERY`; changing `.env` requires restarting the relevant processes. IT resets on each popup opening rather than remembering a previous non-IT selection.

## Implementation Units

### U1. Gate external notifications

**Goal:** Deliver R1–R4 through KTD1.

**Dependencies:** None.

**Files:** `cv_optimizer/config.py`, `server.py`, `cv_optimizer/discovery/notify.py`, `.env.example`, `README.md`, `tests/test_notifications.py`, `tests/test_profile_generation.py`.

**Approach:** Guard the Discord and desktop delivery helpers. Consolidate the server's direct desktop calls behind a guarded helper while retaining best-effort completion semantics. Update tests that explicitly exercise enabled delivery to opt in. Document the default and restart behavior.

**Patterns:** Existing `_env_flag`, `send_discord_notification`, `_notify_document_ready`, discovery notification helpers.

**Test scenarios:**
1. Without the flag, or with a false value, no HTTP or desktop subprocess delivery occurs, including with a configured webhook.
2. With the flag enabled, completion and discovery deliver to both channels; missing webhook skips Discord only.
3. Generation and cover-letter failures stay externally silent when disabled.
4. Enabled delivery failures retain best-effort generation behavior.

**Verification:** Focused notification and profile-generation tests pass with delivery mocked; no real webhook or desktop notification is sent.

### U2. Default extension profile to IT

**Goal:** Deliver R5–R6 through KTD2.

**Dependencies:** None; independent of U1.

**Files:** `extension/popup.html`, `extension/popup.js` (verification only), `tests/test_profile_requests.py` (existing behavior reference).

**Approach:** Set the native selected option and smoke-test the real popup with mocked extension API and backend delivery.

**Test scenarios:**
1. Opening the popup selects IT, and extraction and manual submissions carry `cv_profile: "it"`.
2. Changing the selection sends the chosen non-IT profile; reopening resets to IT.

**Verification:** Browser evidence covers popup defaults and submission payloads. No permanent unit test is required for this native HTML default.

## Verification Contract

Run `python3 -m pytest tests/test_notifications.py tests/test_profile_generation.py tests/test_profile_requests.py tests/test_discovery_integration.py -q`, then `python3 -m pytest tests/ -q` if focused checks pass. Use browser smoke verification for U2 and check `git diff --check`. Isolate failures from pre-existing local changes and never send real notifications during tests.

## Definition of Done

Both units meet their requirements and verification outcomes. Documentation explains opt-in behavior. The diff contains no abandoned approaches or unrelated local work. Independent review findings are resolved or durably recorded before PR publication.
