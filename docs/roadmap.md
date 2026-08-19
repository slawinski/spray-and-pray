# CV Optimizer & Application Pipeline Roadmap

**Vision:** Transform the manual CV Optimizer CLI into a frictionless, semi-autonomous job application engine, progressively replacing manual steps with automation.

---

## 📝 To-Do / Ideas

- [ ] Ship as a paid product
- [ ] Auto-scrape job descriptions and feed them into the pipeline
- [ ] Mention in deliverables that the CV was optimized by bespoke software

---

## ✅ Milestone 0: Core CV Optimizer CLI (Completed)
**Objective:** A foundational command-line tool that takes a master CV and a job description, uses an LLM to tailor the CV to the specific role, and generates a formatted PDF.

### Architecture Components
- **CLI Interface:** A Python terminal application (`cv-opt`) for manual triggering and tracking.
- **LLM Engine:** Connects to an LLM provider to rewrite bullet points, align keywords, and restructure sections based on the target Job Description.
- **Local Database:** SQLite database to track applications, statuses, and generated CV paths.
- **PDF Generator:** Compiles the tailored CV data into a styled PDF document.

### Implementation Steps
- [x] **Step 0.1:** Define the Master CV JSON structure.
- [x] **Step 0.2:** Implement the LLM prompt chain for tailoring experience and skills.
- [x] **Step 0.3:** Build the PDF compilation pipeline.
- [x] **Step 0.4:** Implement the SQLite database to persist application records.
- [x] **Step 0.5:** Wrap in a clean CLI interface with `track` and `status` commands.

---

## ✅ Milestone 1: The Frictionless "1-Click" Trigger (Done)
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
- [x] **Step 1.1:** Build the local FastAPI server with a single `/api/track` endpoint.
- [x] **Step 1.2:** Modify the local server to trigger the `cv-opt` pipeline and handle success/failure states.
- [x] **Step 1.3:** Set up a Telegram Bot or Discord Webhook and integrate the HTTP request into the server's success flow.
- [x] **Step 1.4:** Create the browser extension (manifest.json, popup.html, content.js) to scrape LinkedIn/Indeed and hit `http://localhost:8000/api/track`.

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

## Milestone 6: Terminal UI Dashboard
**Objective:** Replace the flat CLI (`track`, `status`) with an interactive terminal dashboard for browsing, filtering, and managing applications — no browser needed.

### Architecture Components
- **TUI Framework:** A Python terminal library (`textual` or `rich.panel`/`rich.table`) providing keyboard-driven navigation through application records, PDF previews, and inline status editing.
- **Live Data Layer:** Queries the local SQLite DB in real time (no reload), rendered as paginated tables with search/filter bars for company, status, date range.
- **Actions Panel:** Context-sensitive keybindings — `A` to apply (opens the extension flow summary), `I` to log interview notes, `E` to review/reject email drafts, `Ctrl+R` to re-generate a CV.
- **Notification Ticker:** A scrolling footer showing incoming notifications (from Discord/Telegram listener) alongside active operations — "Generating CV…", "Applied to X", "Email received from Y".

### Implementation Steps
- [ ] **Step 6.1:** Scaffold the TUI framework (`textual` app with layout: header ticker / body table / footer status).
- [ ] **Step 6.2:** Implement paginated application table with keyboard navigation and inline search/filter.
- [ ] **Step 6.3:** Add context-sensitive action handler (apply, review, log notes, regenerate CV) bound to single keys.
- [ ] **Step 6.4:** Wire up the notification ticker from the existing Telegram/Discord listener into the footer panel.

---

## Milestone 7: Mock Interview & Preparation Review
**Objective:** From any tracked application in the dashboard, trigger an interactive mock interview session that opens in the browser — simulating role-specific questions, live coding challenges, and personalized feedback to fully prepare the candidate for the role described in the Job Description.

### Architecture Components
- **LLM Interview Generator:** Given the Job Description and Master CV, the LLM generates role-specific questions (behavioral, technical, system design) and live coding prompts directly relevant to the target role. If the company has a known recruitment process (e.g., multi-stage interviews, take-home assignments, specific interview formats) or if an interview guide from sources like Glassdoor / interview reports is available, the session structure and questions should reflect that format accordingly.
- **Web-Based Interview Session:** A lightweight web app (FastAPI + Jinja2 or a static page) launched by the dashboard, presenting one question at a time with:
  - Question prompt and expected answer structure
  - Built-in code editor for live coding exercises
  - Hint/reveal button with guided answer framework
  - Session timer and pacing guide
- **Session Report & Readiness Score:** After completion, the system produces a scored report with answer feedback, coding exercise evaluation, suggested improvements, and an overall readiness score for that specific application.

### Workflow
1. User presses a keybinding (e.g., `P`) on a tracked application in the TUI dashboard.
2. System generates a mock interview session via the LLM, tailored to that application's Job Description and the candidate's Master CV.
3. Browser opens to a local web page with the interactive interview interface.
4. User completes questions and coding exercises at their own pace.
5. System saves the session report and logs it as a note in the application's status history.
6. Dashboard shows a "readiness score" or preparation indicator for each application.

---

## Milestone 8: Learning Aide — Interactive Skill-Builder
**Objective:** Turn interview weaknesses into learning opportunities. From any hint or evaluation weakness, generate a blog-like interactive lesson with live code examples using Monaco Editor. Build a personal lesson library that grows as the candidate encounters new concepts.

### Architecture Components
- **LLM Lesson Generator:** Given a concept (e.g., "idempotency in message queues") and interview context, generates a structured tutorial with explanations, code examples, common pitfalls, and an interview angle section.
- **Interactive Lesson Page:** Blog-style article with embedded Monaco Editor instances for each code example. "Show Solution" toggle reveals reference implementation and LLM-generated explanation.
- **Touchpoints:** Triggered from (a) hint panel "Deep Dive →" links during mock interviews, (b) evaluation report weakness links, (c) standalone lesson library via TUI keybinding `[L]`.
- **Lesson Library:** `/learn` page listing all generated lessons with difficulty badges, read time, and related concept tags. Grows organically — no hand-curated content.

### Workflow
1. Candidate misses a concept during mock interview → evaluation shows weakness.
2. Candidate clicks "Deep Dive →" next to the weakness (or from hint panel during session).
3. System generates a blog-like lesson via LLM with interactive code example.
4. Browser opens the lesson — candidate reads, edits code, toggles solution.
5. Lesson persisted in library → browsable from TUI `[L]` keybinding.

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
