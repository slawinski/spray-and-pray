# Milestone 7: Mock Interview & Preparation Review (SAP) Specification

**Status:** Draft
**Dependencies:** Milestone 0 (CLI, DB, LLM pipeline), Milestone 1 (FastAPI server, browser extension), Milestone 6 (TUI Dashboard)
**Framework:** [Textual](https://textual.textualize.io) v6.6+, [FastAPI](https://fastapi.tiangolo.com/) (existing), [Monaco Editor](https://microsoft.github.io/monaco-editor/) via CDN
**Application Name:** Spray And Pray (abbreviated **SAP** or **sap**)

---

## Problem Statement

The current pipeline generates tailored CVs and tracks applications, but does nothing to prepare the candidate for the actual interview. The user must manually search for company interview guides on Glassdoor, guess what questions might be asked, and practice coding exercises in a separate environment. There is no integrated way to:

1. Generate role-specific interview questions from the same JD that was used to tailor the CV.
2. Practice answering in a structured session with hints and pacing.
3. Write and run live code against the exact technologies mentioned in the JD.
4. Receive a scored evaluation that measures readiness for that specific role.

The TUI dashboard already shows every tracked application — it is the natural launchpad for a targeted mock interview session.

---

## Goals

- [ ] From any tracked application in the TUI dashboard, launch an interactive browser-based mock interview session with a single keybinding.
- [ ] Generate role-specific questions (behavioral, technical, system design) and live coding prompts from the Job Description and Master CV via the LLM.
- [ ] If the company has a known interview process (sourced from Glassdoor, company career pages, or manually provided), structure the session to match that format.
- [ ] Provide a built-in code editor (Monaco) for live coding exercises with syntax highlighting and language support matching the JD.
- [ ] Evaluate the candidate's answers and coding exercises via LLM, producing a scored readiness report per application.
- [ ] Display a readiness indicator in the TUI dashboard for each application.
- [ ] Persist all session data (questions, answers, scores) so the candidate can revisit and improve.

---

## Out of Scope

- Real-time collaborative interviewing (this is a solo preparation tool).
- Code execution and auto-grading (the LLM evaluates code, not a test harness).
- Video or voice recording — text and code only.
- Automated Glassdoor scraping — company interview processes are provided manually or via a static JSON config.
- Interview scheduling or calendar integration (see Milestone 2 for email parsing and Calendly).
- Mobile-friendly interview interface — the session is designed for a desktop browser with a full keyboard.

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          SAP TUI Dashboard                         │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  DataTable                                        Press [P]   │ │
│  │  ┌──────┬──────────┬──────────────┬───────────┬────────────┐ │ │
│  │  │  #   │ Company  │     Role     │  Status   │  Readiness │ │ │
│  │  ├──────┼──────────┼──────────────┼───────────┼────────────┤ │ │
│  │  │  1   │ Acme Inc │ Sr. Engineer │ interview │  ██████░░  │ │ │
│  │  └──────┴──────────┴──────────────┴───────────┴────────────┘ │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                          opens browser                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Browser (localhost:8000)                         │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │              Mock Interview Session                            │ │
│  │  ┌─────────────────────────────────────────────────────────┐  │ │
│  │  │  Question 3 / 8                              ⏱ 04:32    │  │ │
│  │  │                                                          │  │ │
│  │  │  "How would you architect a real-time notification       │  │ │
│  │  │   pipeline handling 2M+ events/day?"                     │  │ │
│  │  │                                                          │  │ │
│  │  │  ┌────────────────────────────────────────────────────┐  │  │ │
│  │  │  │ (Text area or Monaco editor for answer)             │  │  │ │
│  │  │  │                                                     │  │  │ │
│  │  │  │                                                     │  │  │ │
│  │  │  └────────────────────────────────────────────────────┘  │  │ │
│  │  │                                                          │  │ │
│  │  │  [ Show Hint ]           [ ← Back ]   [ Next → ]         │  │ │
│  │  └─────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Server (existing)                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Interview Gen    │  │ Session Manager  │  │ Evaluation Engine│  │
│  │ (LLM)            │  │ (in-memory state)│  │ (LLM)            │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SQLite DB                                   │
│  ┌────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ applications       │  │ interview_sessions                   │  │
│  │ (existing)         │  │ (new)                                │  │
│  └────────────────────┘  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
cv_optimizer/
├── interview.py              ← LLM interview generator & evaluator
├── db.py                     ← Add interview_sessions table + queries
├── prompts/
│   ├── interview-generator.md  ← System prompt for question generation
│   └── interview-evaluator.md  ← System prompt for answer evaluation
│
templates/
├── interview.html              ← Jinja2 template for interview UI
│
static/
└── interview.js                ← Frontend logic (question flow, Monaco)
│
server.py                       ← New routes: /api/interview/*
│
cv_optimizer/tui/
└── app.py                      ← Keybinding [P], readiness column
```

### Data Flow

```
1. User presses [P] in TUI on application #42
       │
2. TUI → GET /api/interview/42/start
       │
3. Server reads JD from disk, Master CV from master_cv.json,
   company intel from company_intel.json (if exists)
       │
4. LLM generates questions → returns JSON array of question objects
       │
5. Server creates interview_sessions row, returns session_id + questions
       │
6. TUI opens browser → http://localhost:8000/interview/{session_id}
       │
7. User answers questions one-by-one, submits session
       │
8. POST /api/interview/{session_id}/evaluate
       │
9. LLM evaluates answers → produces scores + readiness_score
       │
10. Server updates interview_sessions row, returns report
       │
11. TUI refreshes → readiness column updated
```

---

## Data Model

### New Table: `interview_sessions`

```sql
CREATE TABLE IF NOT EXISTS interview_sessions (
    id              INTEGER PRIMARY KEY,
    application_id  INTEGER NOT NULL,
    questions_json  TEXT NOT NULL,          -- JSON array of question objects
    answers_json    TEXT,                   -- JSON array of answer objects (nullable until completed)
    scores_json     TEXT,                   -- JSON evaluation results (nullable until evaluated)
    readiness_score INTEGER,               -- 0-100 overall readiness
    report_text     TEXT,                   -- LLM-generated feedback report
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at    DATETIME,
    FOREIGN KEY (application_id) REFERENCES applications(id)
);
```

### Question Object Schema

```json
{
  "id": 1,
  "type": "behavioral | technical | system_design | coding",
  "prompt": "How would you architect a real-time notification pipeline handling 2M+ events/day?",
  "context": "The role requires experience with Kafka, WebSockets, and Postgres.",
  "hint": "Consider message durability, back-pressure, and delivery guarantees.",
  "language": "javascript",          // Only for coding type questions
  "starter_code": "function process() {\n  // TODO\n}",
  "expected_concepts": ["message queues", "pub/sub", "idempotency"],
  "time_estimate_seconds": 300
}
```

### Answer Object Schema

```json
{
  "question_id": 1,
  "answer_text": "I would use Kafka for message ingestion...",
  "code": "function process() { ... }",   // Only for coding questions
  "time_spent_seconds": 245
}
```

### Evaluation Schema

```json
{
  "question_id": 1,
  "score": 85,
  "feedback": "Strong understanding of message durability. Consider mentioning dead-letter queues.",
  "strengths": ["Correctly identified pub/sub pattern", "Covered back-pressure"],
  "weaknesses": ["Did not mention idempotency for at-least-once delivery"]
}
```

---

## Implementation Steps

### Step 7.1 — Interview Question Generator

**Objective:** Create a Python module that takes a Job Description, Master CV, and optional company interview guide and produces a JSON array of role-specific interview questions via the LLM.

**Tasks:**
- Create `cv_optimizer/interview.py` with `InterviewGenerator` class.
- Design `cv_optimizer/prompts/interview-generator.md` — the system prompt that instructs the LLM to:
  - Extract top technologies, skills, and domain concepts from the JD.
  - Cross-reference the Master CV to identify areas where the candidate has experience (to ask probing questions) and gaps (to ask how they'd bridge them).
  - Generate 6-10 questions distributed across question types:
    - **Behavioral (30%)** — STAR-format questions tied to the role (e.g., "Tell me about a time you shipped under a tight deadline").
    - **Technical (40%)** — Deep dives into technologies listed in the JD.
    - **System Design (20%)** — Architecture questions relevant to the role's scope.
    - **Coding (10%)** — A focused coding prompt using a language from the JD.
  - For each question, provide: `type`, `prompt`, `hint`, `expected_concepts` (what a strong answer should cover), `time_estimate_seconds`.
  - For coding questions, additionally provide: `language`, `starter_code`.
  - If a `company_intel` object is provided, weight question types and format to match that company's known process (e.g., if the company is known for take-home assignments, include a longer coding prompt; if known for case-study interviews, generate a case-study question).
- Implement `InterviewGenerator.generate(app_id: int) -> dict` that:
  1. Reads the JD and Master CV.
  2. Checks for company interview intel in `company_intel.json` keyed by company name (fuzzy match).
  3. Calls the LLM with the combined context.
  4. Parses the JSON response into a validated question array.
  5. Returns `{ "session_id": ..., "questions": [...] }`.

**Verification:**
- Run `python -c "from cv_optimizer.interview import InterviewGenerator; ..."` with a real application and verify the JSON output matches the schema.
- Spot-check that questions reference technologies from the JD, not random technologies.
- Verify that coding questions include `starter_code` and `language` fields.

---

### Step 7.2 — Interview Session Web Server

**Objective:** Add FastAPI routes to the existing `server.py` to manage interview sessions (create, resume, submit answers, evaluate).

**Tasks:**

#### 7.2a — Static Files & Templates

- Install Jinja2: `pip install jinja2`.
- Mount a static directory in `server.py`:
  ```python
  from fastapi.staticfiles import StaticFiles
  from fastapi.templating import Jinja2Templates

  app.mount("/static", StaticFiles(directory="static"), name="static")
  templates = Jinja2Templates(directory="templates")
  ```
- Create `templates/interview.html` — the main Jinja2 template for the interview UI.
- Create `static/interview.js` — frontend logic.

#### 7.2b — Session Routes

Add the following routes to `server.py`:

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/interview/{app_id}/start` | Generate questions, create session, return session_url |
| `GET` | `/interview/{session_id}` | Serve the interactive interview HTML page |
| `POST` | `/api/interview/{session_id}/answer` | Save an answer for a specific question (progressive save) |
| `POST` | `/api/interview/{session_id}/evaluate` | Submit all answers for LLM evaluation, return report |
| `GET` | `/api/interview/{session_id}/report` | View the evaluation report (HTML) |
| `GET` | `/api/interview/{app_id}/latest` | Get the latest session readiness score for the TUI dashboard |

**`POST /api/interview/{app_id}/start`** flow:
1. Validate `app_id` exists in DB.
2. Lock: if an in-progress session exists for this app, return its `session_url` instead of creating a new one.
3. Call `InterviewGenerator.generate(app_id)`.
4. Insert row into `interview_sessions`.
5. Return `{ "session_id": 42, "session_url": "http://localhost:8000/interview/42" }`.

**`GET /interview/{session_id}`** flow:
1. Load session from DB.
2. Render `interview.html` with the session's questions as JSON embedded in the page.

**`POST /api/interview/{session_id}/answer`** flow:
1. Accept `{ "question_id": 1, "answer_text": "...", "code": "..." }`.
2. Validate the question belongs to this session.
3. Append/replace the answer in the session's `answers_json`.
4. Return `{ "ok": true }`.

**`POST /api/interview/{session_id}/evaluate`** flow:
1. Load session data (questions + answers).
2. Lock: only evaluate sessions with all questions answered.
3. Call the Evaluation Engine (Step 7.4).
4. Update `scores_json`, `readiness_score`, `report_text`, `completed_at` in the DB.
5. Return the evaluation report.

**Verification:**
- Start the server, hit `/api/interview/1/start` with curl and verify a 200 response with a valid `session_url`.
- Open the returned URL in a browser, verify the interview page renders with questions.
- Submit a few answers via the `/answer` endpoint, verify they persist.

---

### Step 7.3 — Interview Frontend

**Objective:** Build the browser-based interview UI with question flow, text answers, live coding with Monaco Editor, hints, timer, and progress indicator.

**Tasks:**

#### 7.3a — HTML Template (`templates/interview.html`)

- Jinja2 template that receives `session` context with `questions` array.
- Layout sections:
  - **Header:** Application company, role, session progress bar (`Question 3 / 8`).
  - **Question Card:** The current question's prompt, type badge, and context.
  - **Answer Area:** A textarea for behavioral/technical/system-design questions, or the Monaco Editor container for coding questions.
  - **Action Bar:** Hint button, Back/Next navigation, Submit for Evaluation button.
  - **Timer:** Session timer in the header (optional, can be hidden).
- Embed all question data as a JavaScript variable for the frontend to consume without additional API calls.

#### 7.3b — Frontend Logic (`static/interview.js`)

- Vanilla JavaScript (no framework — keep it simple and dependency-free like the extension).
- **State management:** Track `currentQuestionIndex`, `answers` object (keyed by question_id).
- **Question navigation:** Back/Next buttons. Answers are auto-saved on navigation via `POST /api/interview/{session_id}/answer`.
- **Hint system:** Initially hidden. Reveal on button click. Show `hint` text and `expected_concepts` list.
- **Timer:** Display elapsed time. Timer is informational only — no auto-submit.
- **Monaco Editor integration:**
  - For coding questions: replace the textarea with a Monaco Editor instance.
  - Load Monaco via ESM CDN:
    ```html
    <script type="module">
      import * as monaco from 'https://cdn.jsdelivr.net/npm/monaco-editor@0.50.0/+esm';
      const editor = monaco.editor.create(document.getElementById('monaco-container'), {
        value: starterCode,
        language: questionLanguage,
        theme: 'vs-dark',
        minimap: { enabled: false },
        automaticLayout: true
      });
    </script>
    ```
  - Set `language` based on the question's `language` field.
  - Set `value` to the question's `starter_code`.
- **Submit flow:** When all questions are answered, show the "Submit for Evaluation" button. On click, send `POST /api/interview/{session_id}/evaluate` and redirect to the report page.

#### 7.3c — Report Page (`templates/interview_report.html`)

- Displays the evaluation report: overall readiness score (0-100), per-question scores, strengths, weaknesses, and the LLM-generated feedback report.
- Readiness score rendered as a visual bar: `████████░░ 78%`.
- Button to return to the TUI or start a new session.

**Verification:**
- Open an interview session in the browser. Navigate through all questions, verify answers persist.
- Answer a coding question, verify Monaco Editor loads with correct language and starter code.
- Submit for evaluation, verify the report page renders with scores and feedback.

---

### Step 7.4 — LLM Evaluation Engine

**Objective:** Create a module that evaluates interview answers against expected concepts and produces a scored readiness report.

**Tasks:**
- Add `InterviewEvaluator` class to `cv_optimizer/interview.py`.
- Design `cv_optimizer/prompts/interview-evaluator.md` — the system prompt that instructs the LLM to:
  - For each question, compare the candidate's answer against the `expected_concepts`.
  - Score each answer 0-100.
  - Produce `strengths` (what was well-covered) and `weaknesses` (what was missed or could be improved).
  - For coding questions, evaluate code structure, readability, and whether it addresses the prompt. Note: the LLM does NOT execute code — it evaluates code quality and correctness through reasoning.
  - Generate an overall `readiness_score` (0-100) with a summary `report_text` paragraph.
  - The readiness score should weigh: technical accuracy (40%), completeness vs expected concepts (30%), communication/clarity (20%), and code quality where applicable (10%).
- Implement `InterviewEvaluator.evaluate(session_id: int) -> dict` that:
  1. Loads the session's questions and answers.
  2. Calls the LLM with all Q&A pairs.
  3. Parses the JSON response.
  4. Returns the evaluation object.
- Session locking: An evaluated session cannot be re-evaluated (to prevent score manipulation). If the user wants to retry, they must start a new session.

**Verification:**
- Submit a completed session for evaluation. Verify the response contains scores for every question.
- Verify that coding questions receive code-quality feedback, not just "correct/incorrect".
- Verify the readiness score is a reasonable integer 0-100, not a placeholder.

---

### Step 7.5 — TUI Dashboard Integration

**Objective:** Add the mock interview launch keybinding and readiness score column to the existing Textual dashboard.

**Tasks:**
- In `cv_optimizer/tui/app.py`:
  - Add keybinding `P` (or `Ctrl+P`) — "Prepare for interview".
  - On press for the currently selected row:
    1. Show a status message: `"Generating interview questions for [Company]..."`.
    2. Call `POST http://localhost:8000/api/interview/{app_id}/start` via `httpx` or `requests` (synchronous call wrapped in `@work(thread=True)` to avoid blocking the UI).
    3. On success, open the returned `session_url` in the default browser:
       ```python
       import webbrowser
       webbrowser.open(session_url)
       ```
    4. Update the status bar: `"Interview session opened in browser."`.
    5. Refresh the table to reflect the new session.
  - On error (server not running), show an error in the status bar: `"Error: Is the server running? (localhost:8000)"`.
- Add a **Readiness** column to the DataTable (after Status):
  - Query the latest `readiness_score` from `interview_sessions` for each application (or NULL if no sessions).
  - Display as a visual bar: `█████░░ 72` or `-` if no sessions exist.
  - Use `cv_optimizer/db.py` with a new function `get_latest_readiness(app_id: int) -> int | None`.
- Update the footer keybinding hints to include `[P]repare`.

**Verification:**
- Start the TUI, select an application, press `P`. Verify the browser opens to the interview URL.
- Complete the interview, submit for evaluation. Refresh the TUI (`Ctrl+R`). Verify the readiness column updates with a score.
- Verify that pressing `P` on an application with no JD (jd_path is NULL) shows an appropriate error.

---

### Step 7.6 — Company Interview Intel Layer

**Objective:** Allow the system to tailor mock interviews to known company recruitment processes.

**Tasks:**
- Create `company_intel.json` in the project root:
  ```json
  {
    "companies": [
      {
        "name": "Google",
        "aliases": ["Alphabet"],
        "interview_process": [
          { "stage": "phone_screen", "format": "technical", "duration_minutes": 45 },
          { "stage": "onsite_1", "format": "coding", "duration_minutes": 60 },
          { "stage": "onsite_2", "format": "system_design", "duration_minutes": 60 },
          { "stage": "onsite_3", "format": "behavioral", "duration_minutes": 45 }
        ],
        "notes": "Heavy emphasis on data structures and algorithms. System design round focuses on distributed systems.",
        "glassdoor_url": "https://www.glassdoor.com/Interview/Google-Interview-Questions-E9079.htm",
        "known_questions": [
          "Design a URL shortener",
          "Implement a LRU cache"
        ]
      }
    ]
  }
  ```
- In `InterviewGenerator.generate()`:
  - After reading the JD and Master CV, look up the company name in `company_intel.json`.
  - Use fuzzy matching on `name` and `aliases` (e.g., case-insensitive, substring).
  - If a match is found, pass the company's interview process and notes to the LLM as additional context in the prompt.
  - The LLM should:
    1. Match the number and types of questions to the company's stage format (e.g., if the company does 2 coding + 1 system design, generate questions in that proportion).
    2. If the company has `known_questions`, include variations of those questions.
    3. Adjust difficulty and focus based on `notes`.
- The `company_intel.json` file is **manually curated** — no automated scraping. It grows as the user researches companies.

**Verification:**
- Add a company entry for a known company (e.g., Google) to `company_intel.json`.
- Track a job application for that company.
- Generate interview questions. Verify the question types match the company's interview process stages.
- Verify that a company without intel still gets a sensible default question distribution.

---

## Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Browser-based UI, not TUI** | The TUI cannot embed Monaco Editor or render rich interactive UIs. The interview session needs a code editor, visual progress bars, and readable question cards — all better suited to a browser. The TUI is the launcher; the browser is the session runner. |
| 2 | **Monaco Editor via CDN, no bundler** | Keeps the stack simple. No npm, no webpack, no build step. Monaco loads from jsDelivr CDN as an ESM module. The interview UI is a single HTML page with inline scripts. |
| 3 | **LLM evaluates code, does not execute it** | Code execution requires sandboxing (Docker, Firecracker, or a third-party API like Judge0) which adds significant infrastructure complexity. For an interview preparation tool, LLM-based code review (structure, correctness, edge cases) provides sufficient feedback without the risk of running arbitrary code server-side. |
| 4 | **Progressive answer saving via POST** | Answers are saved one at a time as the user navigates through questions. This prevents data loss on browser crash, enables session resumption, and keeps the frontend stateless. |
| 5 | **Session locking (one active per application)** | Starting a new session for an already-in-progress session returns the existing session URL. Evaluated sessions cannot be re-evaluated (must start fresh). This prevents score gaming and keeps the data model simple. |
| 6 | **Company intel is a static JSON file** | Avoiding automated Glassdoor scraping (legal gray zone, anti-bot measures) and API dependencies. The file is manually curated and version-controlled. It grows organically as the user researches companies. |
| 7 | **In-memory session state via DB, not server memory** | Sessions are persisted to SQLite immediately on creation. The FastAPI server can restart without losing session data. No need for Redis or server-side session storage. |
| 8 | **Separate LLM prompts for generation vs evaluation** | Question generation and answer evaluation are fundamentally different tasks. Separate prompts allow independent iteration — you can improve evaluation scoring without touching question generation, and vice versa. |

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM generates irrelevant or overly generic questions | Candidate wastes time on non-targeted practice | The prompt constrains question generation to JD technologies and Master CV context. Verification step includes spot-checking questions. |
| LLM evaluation is too generous or too harsh | Readiness score is misleading | The prompt defines explicit scoring weights. Multiple evaluation runs on the same answers should yield similar scores (deterministic with temperature=0). |
| Monaco Editor CDN is unavailable | Coding questions have no editor | Fallback to a plain `<textarea>` if Monaco fails to load. The frontend detects `typeof monaco === 'undefined'` and degrades gracefully. |
| Server not running when TUI triggers interview | User gets an error with no clear next step | The TUI catches the connection error and displays: "Error: Is the server running? Run `uvicorn server:app` on port 8000." |
| Company intel file grows large and unwieldy | Slower lookups, harder to maintain | Use JSON for now. If it exceeds ~50 companies, migrate to a `company_intel` SQLite table with indexed lookups. |
