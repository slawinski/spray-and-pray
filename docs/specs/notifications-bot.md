# Local API Bridge & Notifications Bot Specification

## Problem Statement
The browser extension needs a backend to receive its data, and the user needs to know when the CV generation is complete without watching a terminal window. We need a local middleware server that triggers the `cv-opt` script and pushes notifications to the user's mobile device via Discord or Telegram.

## Goals
- [ ] Run a local HTTP server that accepts `POST` payloads from the extension.
- [ ] Programmatically trigger the internal `cv_optimizer.tracker.track()` function.
- [ ] Send a push notification (Telegram/Discord) upon completion.

## Out of Scope
- [Explicitly NOT building: Public internet exposure (runs strictly on localhost).]
- [Explicitly NOT building: Receiving inbound commands from Telegram/Discord (handled in Milestone 2).]

---

## User Stories

### P1: Trigger Pipeline via HTTP ⭐ MVP
**User Story**: As a local middleware server, I want to receive job payloads and execute the `tracker.track()` function so that a CV is generated automatically.

**Why P1**: This bridges the gap between the browser and the Python CLI logic.

**Acceptance Criteria**:
1. WHEN a POST request is received at `/api/track` THEN system SHALL write the JD to a temporary file and call `tracker.track()`.
2. WHEN the `track()` function completes THEN system SHALL delete the temporary JD file.

**Independent Test**: Can demo by sending a cURL POST request and observing a new application folder and CV being generated.

---

### P1: Push Notifications on Completion ⭐ MVP
**User Story**: As a job seeker, I want to receive a push notification when my CV is ready so that I know I can proceed with the application.

**Why P1**: Eliminates the need to monitor the local terminal.

**Acceptance Criteria**:
1. WHEN `tracker.track()` succeeds THEN system SHALL send a formatted success message to the configured Discord/Telegram webhook.
2. WHEN `tracker.track()` fails THEN system SHALL send an error notification with the failure reason.

**Independent Test**: Can demo by manually triggering the API and receiving a ping on Discord/Telegram.

---

## Edge Cases
- WHEN the POST payload is missing required fields THEN system SHALL return a 400 Bad Request response.
- WHEN the `cv-opt` generation fails (e.g., Ollama is down) THEN system SHALL catch the exception and send a failure notification via the webhook.
- WHEN the Discord/Telegram webhook URL is misconfigured THEN system SHALL log a warning locally but not crash the main CV generation process.

---

## Success Criteria
How we know the feature is successful:
- [ ] API server handles incoming requests in < 50ms (excluding CV generation time).
- [ ] User reliably receives a push notification on their phone/desktop immediately after CV generation completes.
