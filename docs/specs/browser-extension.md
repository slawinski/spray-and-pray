# CV Optimizer Browser Extension Specification

## Problem Statement
Manually copying job descriptions from LinkedIn or Indeed into a text file and then executing a terminal command is tedious and adds friction to the application process. We need a frictionless, 1-click trigger to initiate the CV generation pipeline directly from the browser.

## Goals
- [ ] Provide a 1-click button to extract job metadata (Company, Role, Job Description) from supported job boards.
- [ ] Automatically send the extracted payload to the local API bridge.

## Out of Scope
- [Explicitly NOT building: Automated submission of the application form.]
- [Explicitly NOT building: Running the LLM or Python scripts inside the browser.]

---

## User Stories

### P1: 1-Click Extraction on LinkedIn ⭐ MVP
**User Story**: As a job seeker, I want to click an extension button on a LinkedIn job posting so that it extracts the job details and triggers the local CV generation pipeline.

**Why P1**: LinkedIn is the primary job board; eliminating manual copy-pasting here solves 80% of the friction.

**Acceptance Criteria**:
1. WHEN the user clicks the extension icon on a LinkedIn job page THEN system SHALL extract Role, Company, and Job Description.
2. WHEN data is extracted THEN system SHALL send a POST request to `http://localhost:8000/api/track`.

**Independent Test**: Can demo by clicking the button on a LinkedIn job and seeing the local API receive the correct JSON payload.

---

### P2: Extensibility for Other Job Boards
**User Story**: As a developer, I want the scraping logic to use a strategy pattern so that I can easily add support for Indeed, Greenhouse, etc.

**Why P2**: Important for future-proofing, but not strictly required for the first MVP.

**Acceptance Criteria**:
1. WHEN the page URL matches a new supported domain THEN system SHALL use the specific selector strategy for that domain.

**Independent Test**: Can demo by adding a dummy strategy for a test page and successfully extracting data.

---

## Edge Cases
- WHEN the user clicks the button on an unsupported website THEN system SHALL display a graceful "Unsupported Job Board" error in the popup.
- WHEN the local API server is down THEN system SHALL display a "Connection Error - Is the local API running?" message.
- WHEN a supported job board changes its DOM structure and extraction fails THEN system SHALL show an error indicating which fields could not be found.

---

## Success Criteria
How we know the feature is successful:
- [ ] User can trigger the full CV generation pipeline from LinkedIn in under 2 seconds (time spent interacting).
- [ ] Zero manual copy-pasting required for supported sites.
