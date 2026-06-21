# Milestone 3: Automated Job Discovery & Scraping Specification

## Problem Statement

Currently, the user must manually browse job boards to find relevant roles, even though the CV generation is automated via the 1-click extension. We want to remove the human from the job discovery phase by automatically aggregating matching jobs from APIs (like SerpApi or RapidAPI) and feeding them directly into the existing CV Optimizer pipeline.

## Goals

- [ ] Automate the discovery of job listings based on specific search criteria (e.g., "Senior Python Remote").
- [ ] Parse and standardize job data (Title, Company, Description) from multiple API sources.
- [ ] Seamlessly integrate with the existing local API (`/api/track`) to trigger CV generation automatically for new jobs.

## Out of Scope

- Scraping websites directly using Playwright/Selenium (we will use APIs to bypass CAPTCHAs).
- Automated submission of the applications to the employer (planned for Milestone 4/5).
- Auto-filtering jobs with an LLM (planned for Milestone 5).

---

## User Stories

### P1: Scheduled Job Fetching ⭐ MVP

**User Story**: As a job seeker, I want a script to periodically fetch jobs from an aggregator API so that I don't have to search job boards manually.

**Why P1**: This is the core functionality of automated job discovery.

**Acceptance Criteria**:

1. WHEN the cron job runs THEN system SHALL query the configured APIs (e.g., SerpApi) for jobs matching predefined keywords.
2. WHEN jobs are returned THEN system SHALL extract the `Job Title`, `Company Name`, and `Job Description`.
3. WHEN a job is already present in the local database THEN system SHALL skip it to prevent duplicates.

**Independent Test**: Can run the aggregator script standalone and see a printed list of parsed, de-duplicated jobs.

---

### P2: Pipeline Integration

**User Story**: As a job seeker, I want the aggregator to send new jobs directly to my local CV Optimizer API so that my CVs are generated automatically.

**Why P2**: Connects the discovery phase to the existing automated CV generation workflow.

**Acceptance Criteria**:

1. WHEN a new unique job is found THEN system SHALL send a POST request to `http://localhost:8000/api/track` with the job details.
2. WHEN the API returns a success response THEN system SHALL log the successful handoff.
3. WHEN the API fails or is unreachable THEN system SHALL log the error and queue the job for the next run.

**Independent Test**: Can mock an API response from the aggregator and verify that the local FastAPI server receives the POST requests and generates CVs.

---

### P3: Multi-Source Support

**User Story**: As a job seeker, I want the system to query multiple APIs (e.g., both Google Jobs via SerpApi and LinkedIn via RapidAPI) so that I have a wider pool of opportunities.

**Why P3**: Nice to have for a larger volume of jobs, but one source is enough for MVP.

**Acceptance Criteria**:

1. WHEN the script runs THEN system SHALL query all enabled sources concurrently or sequentially.
2. WHEN parsing responses THEN system SHALL normalize the data into a standard schema regardless of the source.

---

## Edge Cases

- WHEN an API rate limit is hit THEN system SHALL log a warning, pause execution, and wait until the next scheduled run.
- WHEN a job description is missing or empty in the API response THEN system SHALL skip the job.
- WHEN the local FastAPI server is offline THEN system SHALL save the discovered jobs to a pending queue instead of dropping them.

---

## Success Criteria

How we know the feature is successful:

- [ ] The aggregator script runs reliably via cron without manual intervention.
- [ ] Successfully fetches, parses, and de-duplicates valid jobs on each run.
- [ ] Discovered jobs successfully trigger the existing `/api/track` endpoint, resulting in ready-to-use CVs and Discord notifications.
