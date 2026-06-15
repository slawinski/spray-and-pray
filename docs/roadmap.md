# CV Optimizer & Application Pipeline Roadmap

**Vision:** Transform the manual CV Optimizer CLI into a frictionless, semi-autonomous job application engine, progressively replacing manual steps with automation.

---

## Milestone 1: The Frictionless "1-Click" Trigger (Current Focus)
**Objective:** Eliminate the need to manually copy/paste job descriptions and run terminal commands. You browse job boards normally, click an extension button, and get notified when your optimized CV is ready to upload.

### Architecture Components
1. **Browser Extension (Frontend)**
   - A lightweight Chrome/Firefox extension (Vanilla JS).
   - **Capabilities:** Scrape the current active tab's DOM to extract the `Job Title`, `Company Name`, and the raw text of the `Job Description`.
   - **Action:** Sends a JSON `POST` request to a local server containing the extracted data.
2. **Local API Bridge (Middleware)**
   - A tiny `FastAPI` or `Flask` server running locally on your machine.
   - **Capabilities:** Listens for incoming `POST` requests from the extension.
   - **Action:** Writes the JD to a temporary file, then executes the `./cv-opt track "[Company]" "[Title]" --jd temp.txt` command programmatically via Python's `subprocess` or by directly calling the `track()` function.
3. **Notification System (Output)**
   - Integration with a messaging API (Telegram Bot API or Discord Webhook).
   - **Capabilities:** Once the `cv-opt` command finishes successfully, the local server sends a push notification.
   - **Message Format:** *"✅ CV generated for **[Role]** at **[Company]**. The PDF is ready in `/applications/[id]`. [Link to job board]."*

### Implementation Steps
- [ ] **Step 1.1:** Build the local FastAPI server with a single `/api/track` endpoint.
- [ ] **Step 1.2:** Modify the local server to trigger the `cv-opt` pipeline and handle success/failure states.
- [ ] **Step 1.3:** Set up a Telegram Bot or Discord Webhook and integrate the HTTP request into the server's success flow.
- [ ] **Step 1.4:** Create the browser extension (manifest.json, popup.html, content.js) to scrape LinkedIn/Indeed and hit `http://localhost:8000/api/track`.

---

## Milestone 2: Inbound Email Parsing & Automated Scheduling
**Objective:** Close the feedback loop early. Automatically monitor incoming recruiter emails, update the database status to reflect interviews, and proactively propose *your* Calendly link to recruiters to minimize back-and-forth.

### Architecture Components
- **IMAP Email Listener:** A background Python daemon monitoring your email inbox for replies from ATS platforms or recruiters.
- **LLM Intent Classifier:** Routes incoming email text to the local LLM to classify the intent: `rejection`, `interview_request`, etc.
- **Workflow:**
  1. Script detects an email matching a tracked company.
  2. LLM classifies it as an `interview request` or `rejection`.
  3. Script executes `./cv-opt status [id] "interview 1"` or `"rejected"`.
  4. If it's an interview request, the system drafts and sends an AI-generated email reply enthusiastically accepting the interview and proposing **your** Calendly link for them to book a slot.
  5. Sends a notification: *"🎉 Interview request from **[Company]**. I have replied with your Calendly link!"*

---

## Milestone 3: Automated Job Discovery & Scraping
**Objective:** Replace the need for manual browsing. Automatically aggregate job listings from various sources that match your criteria and feed them into the local API bridge.

### Architecture Components
- **Job Aggregator Script:** A Python cron job that runs periodically to fetch new job listings.
- **Data Sources:** Uses APIs like SerpApi (Google Jobs), RapidAPI (LinkedIn unofficial), or RSS feeds to bypass CAPTCHA and anti-bot measures.
- **Workflow:**
  1. Script queries the API for specific keywords (e.g., "Senior Python Remote").
  2. Parses the JSON response to extract `Job Title`, `Company Name`, and `Job Description`.
  3. Sends a `POST` request to the local API bridge (`http://localhost:8000/api/track`) for each match.
  4. The existing pipeline generates the CV and sends the Discord/Telegram notification.

---

## Milestone 4: Automated Submission for Standardized Forms
**Objective:** Automate the actual submission for ATS platforms that don't try to block bots (e.g., Greenhouse, Lever).

### Architecture Components
- **Playwright Automation Script:** A Python script triggered immediately after CV generation if the job URL matches a known ATS domain.
- **Form Mapping:** A utility that maps `master_cv.json` fields to standard Greenhouse/Lever input `name` attributes.
- **Workflow:** 
  1. Server generates CV.
  2. Server checks URL. If `boards.greenhouse.io`, it launches headless Playwright.
  3. Playwright fills form, uploads the specific `cv.pdf`, and submits.
  4. Server runs `./cv-opt status [id] applied` automatically.
  5. Notification updates to: *"🚀 Automatically applied to **[Role]** at **[Company]**."*

---

## Milestone 5: AI-Driven Autonomous Scraping & Applying (The Final Form)
**Objective:** Fully remove the human from the top of the funnel. You only step in for interviews.

### Architecture Components
- **Cron-Triggered Web Agent:** A script running daily that uses the local `qwen` model and an agent framework (like `browser-use`).
- **Workflow:**
  1. Agent navigates to LinkedIn/Indeed.
  2. Searches for specific queries (e.g., "Senior Frontend Remote").
  3. Evaluates JDs against your Master CV to ensure a minimum match percentage (preventing spam applications).
  4. Triggers the internal CV generation pipeline for approved jobs.
  5. Agent attempts to submit the application natively.
  6. Sends daily digest notification: *"Processed 15 jobs today. Successfully applied to 4. 2 require manual submission."*
