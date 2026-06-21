# Milestone 2: Inbound Email Parsing & Automated Scheduling Specification

## Problem Statement

Following up on job applications is a manual and stressful process. When recruiters reply with interview requests, delays in responding can result in lost opportunities, and the back-and-forth scheduling consumes time. We need to close the feedback loop by automatically monitoring the inbox, classifying responses, and instantly offering a Calendly link for interviews.

## Goals

- [ ] Automate the monitoring of incoming recruiter emails using IMAP.
- [ ] Accurately classify email intent (e.g., `rejection`, `interview_request`) using an LLM.
- [ ] Auto-reply to interview requests with a Calendly link to eliminate scheduling friction.
- [ ] Automatically update the application status in the local database based on the email.

## Out of Scope

- Managing or parsing Google Calendar / Outlook calendar APIs directly (relying entirely on Calendly links).
- Handling complex multi-stage technical assessments or coding challenges via automated replies.
- Sending initial cold-outreach emails (this focuses strictly on inbound replies to existing applications).

---

## User Stories

### P1: IMAP Inbox Monitoring & Database Sync ⭐ MVP

**User Story**: As a job seeker, I want the system to continuously monitor my inbox for emails from tracked companies so that responses are detected immediately.

**Why P1**: Foundation for the entire milestone. Without email ingestion, no automation can occur.

**Acceptance Criteria**:

1. WHEN the background daemon runs THEN system SHALL connect to the configured IMAP inbox.
2. WHEN an unread email arrives THEN system SHALL check if the sender domain or content matches a company in the `applications.db`.
3. WHEN a match is found THEN system SHALL fetch the raw email body and mark it for processing.

**Independent Test**: Can run the IMAP listener and print out detected emails that match a mock company in the database.

---

### P2: LLM Intent Classification

**User Story**: As a job seeker, I want incoming recruiter emails classified by an LLM so that the system knows whether it's a rejection or an interview request.

**Why P2**: Required to determine the correct automated action.

**Acceptance Criteria**:

1. WHEN an email is marked for processing THEN system SHALL send the email body to the local LLM.
2. WHEN the LLM responds THEN system SHALL classify the intent strictly as `interview_request`, `rejection`, or `other`.
3. WHEN the intent is `rejection` THEN system SHALL execute `./cv-opt status [id] "rejected"` and send a Discord notification.

**Independent Test**: Can pass raw email text to the classifier function and assert it returns the correct enum/intent.

---

### P3: Automated Interview Scheduling (Auto-Reply)

**User Story**: As a job seeker, I want the system to instantly reply to interview requests with my Calendly link so that recruiters can book me immediately.

**Why P3**: The ultimate value prop—eliminating the scheduling back-and-forth.

**Acceptance Criteria**:

1. WHEN the intent is `interview_request` THEN system SHALL use the LLM to draft a polite, context-aware acceptance email proposing the user's Calendly link.
2. WHEN the draft is ready THEN system SHALL send the email via SMTP as a reply to the original thread.
3. WHEN the email is sent THEN system SHALL execute `./cv-opt status [id] "interview 1"` and send a Discord notification.

**Independent Test**: Can trigger the auto-reply flow with a dummy email and verify an outbound SMTP request is made containing the Calendly link.

---

## Edge Cases

- WHEN an email is part of a long thread THEN system SHALL parse only the latest reply to avoid confusing the LLM.
- WHEN the LLM classification confidence is low or ambiguous THEN system SHALL default to `other` and notify the user to handle it manually.
- WHEN the SMTP send fails THEN system SHALL log the error and alert the user via Discord to reply manually.
- WHEN multiple applications exist for the same company THEN system SHALL attempt to match based on the job title mentioned in the email or update the most recent one.

---

## Success Criteria

How we know the feature is successful:

- [ ] IMAP daemon successfully ingests recruiter emails with < 5 minute latency.
- [ ] LLM correctly classifies at least 95% of rejections and interview requests.
- [ ] System successfully auto-replies to interview requests with the Calendly link without user intervention.
- [ ] Database statuses stay perfectly synced with inbox reality.
