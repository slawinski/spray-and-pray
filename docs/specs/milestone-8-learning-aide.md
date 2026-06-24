# Milestone 8: Learning Aide — Interactive Skill-Builder (SAP) Specification

**Status:** Draft
**Dependencies:** Milestone 7 (Mock Interview & Preparation Review)
**Framework:** [FastAPI](https://fastapi.tiangolo.com/) (existing), [Monaco Editor](https://microsoft.github.io/monaco-editor/), [Chart.js](https://www.chartjs.org/), [Mermaid](https://mermaid.js.org/) via CDN, Jinja2 (existing)
**Application Name:** Spray And Pray (abbreviated **SAP** or **sap**)

---

## Problem Statement

Milestone 7's mock interviews identify what a candidate doesn't know (weaknesses in evaluations) and offer brief hints during the session. But there is no path from "I missed this concept" to "I now understand and can apply it." The candidate must leave the SAP ecosystem, search the web, find tutorials of unknown quality, and piece together an understanding from scattered sources.

We need a **learning aide** — a blog-like, interactive lesson experience — that takes any concept the candidate struggled with and generates a self-contained tutorial with live, editable code examples. It should feel like a premium coding blog, not a dry textbook.

**Core insight:** The evaluation engine already knows what the candidate missed. The hint system already knows what to hint about. Bridge the gap — turn a hint into a full lesson.

---

## Goals

- [ ] From any weakness in an interview evaluation, or from the hint panel during a session, open a "Deep Dive" lesson that explains the concept in depth.
- [ ] Generate blog-like tutorial content via LLM: explanation, why it matters, step-by-step breakdown, common pitfalls, interactive code examples, charts, diagrams, and dashboards with knobs/sliders.
- [ ] Provide one or more Monaco Editor instances embedded in the lesson for the candidate to explore, modify, and test their understanding of code examples.
- [ ] Render Mermaid diagrams for architecture flows, sequence diagrams, and state machines; Chart.js visualizations for data structures, performance comparisons, and time-series concepts.
- [ ] Support interactive widgets — small dashboards with sliders, knobs, toggles — that let the candidate manipulate variables and see the effect in real time (e.g., throttle a request rate slider and watch a queue backlog chart update).
- [ ] Lessons persist in a searchable, browsable library accessible from the TUI dashboard.
- [ ] Content is scoped to the technologies and concepts relevant to the candidate's job applications — no generic CS 101 content.

---

## Out of Scope

- Code execution in the browser (the LLM evaluates code through reasoning, not sandboxed execution — same constraint as Milestone 7).
- Video, voice, or multimedia content — text, code, and diagrams only.
- A full LMS (Learning Management System) with progress tracking, quizzes, or certifications.
- User-generated content or community features.
- Offline lesson viewing — lessons require the local server and LLM.

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          SAP TUI Dashboard                          │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  DataTable                                       [L]essons   │ │
│  │  ┌──────┬──────────┬──────────────┬───────────┬────────────┐ │ │
│  │  │  #   │ Company  │     Role     │  Status   │  Readiness │ │ │
│  │  └──────┴──────────┴──────────────┴───────────┴────────────┘ │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Browser (localhost:8000)                            │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Interview Session                          │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  Hint Panel                                            │  │   │
│  │  │  ┌──────────────────────────────────────────────────┐  │  │   │
│  │  │  │ "Consider message durability, back-pressure,     │  │  │   │
│  │  │  │  and delivery guarantees."                       │  │  │   │
│  │  │  │  [idempotency] [pub/sub] [dead-letter]          │  │  │   │
│  │  │  │                                                  │  │  │   │
│  │  │  │  → [Deep Dive: Understanding Message Durability] │  │  │   │
│  │  │  └──────────────────────────────────────────────────┘  │  │   │
│  │  └──────────────────────────────────────────────────────┘  │  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                               │                                     │
│                               ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Learning Lesson                            │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  # Understanding Message Durability                     │  │   │
│  │  │  [5 min read] [Difficulty: Intermediate]               │  │   │
│  │  │                                                        │  │   │
│  │  │  Message durability ensures that once a message is     │  │   │
│  │  │  accepted by the broker, it will not be lost even if   │  │   │
│  │  │  the broker crashes. This is critical because...       │  │   │
│  │  │                                                        │  │   │
│  │  │  ## Why It Matters in Interviews                       │  │   │
│  │  │  ...                                                    │  │   │
│  │  │                                                        │  │   │
│  │  │  ## Try It Yourself                                     │  │   │
│  │  │  ┌──────────────────────────┬────────────────────────┐  │  │   │
│  │  │  │  Your Code (editable)    │  Expected Output       │  │  │   │
│  │  │  │  ┌────────────────────┐  │  ┌──────────────────┐  │  │  │   │
│  │  │  │  │ fn process(msg) {  │  │  │ ✓ Message 1 ack'd │  │  │  │   │
│  │  │  │  │  // your code      │  │  │ ✓ Message 2 ack'd │  │  │  │   │
│  │  │  │  │ }                  │  │  │ ✗ Message 3: fail │  │  │  │   │
│  │  │  │  └────────────────────┘  │  │  → retry queued   │  │  │  │   │
│  │  │  └──────────────────────────┴────────────────────────┘  │  │   │
│  │  │                                                        │  │   │
│  │  │  ## Common Pitfalls                                     │  │   │
│  │  │  ...                                                    │  │   │
│  │  │                                                        │  │   │
│  │  │  ## Interview Angle                                     │  │   │
│  │  │  ...                                                    │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Evaluation Report                          │   │   │
│  │  Weakness: "Did not address idempotency"                     │   │   │
│  │  → [Deep Dive: Idempotency in Distributed Systems]           │   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Server (existing)                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Lesson Generator │  │ Lesson Library   │  │ Evaluation Link  │  │
│  │ (LLM)            │  │ (DB queries)     │  │ (weakness→lesson)│  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SQLite DB                                   │
│  ┌────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ interview_sessions │  │ lessons                              │  │
│  │ (existing)         │  │ (new)                                │  │
│  └────────────────────┘  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
cv_optimizer/
├── interview.py              ← Add: InterviewGenerator.generate_lesson()
├── prompts/
│   └── lesson-generator.md   ← System prompt for lesson generation
│
templates/
├── interview.html              ← Add: "Deep Dive" link in hint panel
├── interview_report.html       ← Add: "Deep Dive" link per weakness
└── lesson.html                 ← New: blog-like lesson template
│
static/
├── lesson.js                   ← New: Monaco editor, Chart.js, Mermaid, widget management
│
server.py                       ← New routes: /api/learn/*, /learn/*
│
cv_optimizer/tui/
└── app.py                      ← New keybinding [L] for lesson library
```

### Data Flow

```
1. Candidate misses concept → evaluation shows weakness
       │
2. Candidate clicks "Deep Dive →" next to weakness
       │
3. POST /api/learn/generate { concept: "idempotency", context: "message queues" }
       │
4. LLM generates blog-like lesson → returns lesson_id
       │
5. Browser redirects → /learn/{lesson_id}
       │
6. Candidate reads, edits code examples, explores
       │
7. Lesson persisted → browsable from dashboard [L]essons library
```

---

## Data Model

### New Table: `lessons`

```sql
CREATE TABLE IF NOT EXISTS lessons (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER,                    -- NULL if standalone (not from a session)
    application_id  INTEGER,                    -- NULL if standalone
    concept         TEXT NOT NULL,              -- e.g., "idempotency in message queues"
    content_json    TEXT NOT NULL,              -- LLM-generated lesson (sections, code examples)
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES interview_sessions(id),
    FOREIGN KEY (application_id) REFERENCES applications(id)
);
```

### Lesson Content Schema

The LLM generates a JSON object with these fields:

```json
{
  "title": "Understanding Idempotency in Distributed Message Queues",
  "difficulty": "intermediate",
  "read_time_minutes": 5,
  "sections": [
    {
      "heading": "What is Idempotency?",
      "body": "Idempotency means that performing the same operation multiple times produces the same result as performing it once. In message queues, this is critical because..."
    },
    {
      "heading": "Why It Matters in Interviews",
      "body": "Interviewers test idempotency to assess whether you think about failure modes. A strong answer covers..."
    },
    {
      "heading": "Try It Yourself",
      "type": "interactive",
      "description": "Modify the handler below to make message processing idempotent. The key insight: track processed message IDs and skip duplicates.",
      "language": "javascript",
      "starter_code": "const processed = new Set();\n\nfunction handleMessage(msg) {\n  // Check if already processed\n  \n  \n  // Process the message\n  console.log('Processing:', msg.id);\n  \n}",
      "expected_output": "Processing: msg-1\nSkipping duplicate: msg-1\nProcessing: msg-2",
      "solution_code": "const processed = new Set();\n\nfunction handleMessage(msg) {\n  if (processed.has(msg.id)) {\n    console.log('Skipping duplicate:', msg.id);\n    return;\n  }\n  processed.add(msg.id);\n  console.log('Processing:', msg.id);\n}",
      "explanation": "The Set data structure provides O(1) lookup. We check before processing and skip if already seen. This guarantees at-most-once processing semantics."
    },
    {
      "heading": "Message Throughput vs Duplicate Rate",
      "type": "chart",
      "chart_type": "line",
      "chart_config": {
        "labels": ["10 msg/s", "100 msg/s", "500 msg/s", "1000 msg/s", "5000 msg/s"],
        "datasets": [{
          "label": "With Idempotency",
          "data": [0, 0, 1, 2, 4],
          "borderColor": "#3fb950",
          "backgroundColor": "rgba(63,185,80,0.1)",
          "tension": 0.3
        }, {
          "label": "Without Idempotency",
          "data": [0, 3, 15, 45, 220],
          "borderColor": "#f85149",
          "backgroundColor": "rgba(248,81,73,0.1)",
          "tension": 0.3
        }]
      },
      "chart_options": { "responsive": true, "scales": { "y": { "title": { "text": "Duplicate Messages", "display": true } } } },
      "caption": "Higher throughput amplifies the duplicate problem. Idempotent consumers keep duplicates near zero regardless of message rate."
    },
    {
      "heading": "At-Least-Once vs Exactly-Once Delivery",
      "type": "diagram",
      "diagram_type": "mermaid",
      "diagram_code": "sequenceDiagram\n    participant Producer\n    participant Broker\n    participant Consumer\n    Producer->>Broker: Publish msg-1\n    Broker->>Consumer: Deliver msg-1\n    Consumer-->>Broker: ACK msg-1\n    Note over Broker: ACK lost (network)\n    Broker->>Consumer: Re-deliver msg-1\n    Consumer->>Consumer: Check dedup cache\n    Consumer-->>Broker: ACK (already processed)\n    Note over Consumer: Idempotent — no duplicate processing",
      "caption": "Sequence diagram showing how idempotent consumers handle at-least-once delivery without processing duplicates."
    },
    {
      "heading": "Experiment: Throttle vs Queue Backlog",
      "type": "interactive_widget",
      "widget_id": "throttle-sim",
      "description": "Adjust the consumer throttle rate below and watch how the queue backlog grows. This demonstrates why pure throttling alone doesn't solve the duplicate problem — you need idempotency regardless of throughput.",
      "controls": [
        { "type": "range", "id": "throttle-rate", "label": "Consumer Throttle (msg/s)", "min": 1, "max": 1000, "step": 10, "default": 100 },
        { "type": "range", "id": "producer-rate", "label": "Producer Rate (msg/s)", "min": 1, "max": 1000, "step": 10, "default": 500 },
        { "type": "toggle", "id": "idempotency-on", "label": "Idempotency Enabled", "default": false }
      ],
      "outputs": [
        { "type": "value", "id": "backlog", "label": "Queue Backlog", "unit": "messages", "compute": "max(0, producerRate - throttleRate) * (idempotencyOn ? 0.5 : 1)" },
        { "type": "value", "id": "duplicates", "label": "Duplicates/Hour", "unit": "", "compute": "idempotencyOn ? 0 : max(0, producerRate - throttleRate) * 3.6" }
      ],
      "insight": "Even with low throttle, the producer rate outpaces consumption. Without idempotency, duplicates compound. Toggle idempotency on and watch duplicates drop to zero — the backlog still exists, but every message is processed exactly once."
    },
    {
      "heading": "Common Pitfalls",
      "body": "1. Relying on database unique constraints alone (what if the insert succeeds but the acknowledgement fails?).\n2. Using in-memory state without persistence (what if the server restarts?).\n3. Confusing idempotency with deduplication — they solve different problems."
    },
    {
      "heading": "Interview Angle",
      "body": "When asked about message reliability, structure your answer as: (1) define the guarantee level (at-most-once, at-least-once, exactly-once), (2) explain how idempotent consumers enable at-least-once with exactly-once semantics, (3) give a concrete example from your experience."
    }
  ],
  "related_concepts": ["message durability", "dead-letter queues", "exactly-once semantics"],
  "source_concepts": ["idempotency", "message queues", "distributed systems"]
}
```

---

## Implementation Steps

### Step 8.1 — Lesson Generator LLM Prompt

**Objective:** Create the system prompt that instructs the LLM to generate blog-quality, interactive tutorial lessons.

**Tasks:**
- Create `cv_optimizer/prompts/lesson-generator.md`.
- The prompt should instruct the LLM to:
  - Take a `concept` (e.g., "idempotency in message queues") and optional `context` (e.g., "missed in a system design interview about Kafka").
  - Generate a JSON lesson object matching the schema above with 6-10 sections.
  - Include at least one `interactive` section (code, chart, or widget) that lets the candidate explore the concept hands-on.
  - When the concept involves data, performance, or trade-offs: include a `chart` section using Chart.js (line, bar, radar, pie, doughnut, scatter). Provide complete `chart_config` JSON (labels, datasets with colors, options).
  - When the concept involves flows, state machines, or architecture: include a `diagram` section with Mermaid syntax (sequenceDiagram, flowChart, stateDiagram, graph, classDiagram).
  - When the concept has tunable parameters (e.g., request rate, cache size, timeouts): include an `interactive_widget` section with HTML form controls (range, toggle, select) and JavaScript `compute` expressions that recalculate outputs in real time as the candidate drags sliders.
  - Include exactly one `interactive` section with `starter_code` (incomplete, for the candidate to fill), `solution_code` (complete reference), `expected_output`, and an `explanation` of why the solution works.
  - Write in a conversational, blog-like tone — accessible but not dumbed-down.
  - Scope examples to the technologies in the candidate's job applications (pulled from the JD and Master CV context).
  - Include a `## Interview Angle` section that directly maps the concept to how it would be tested in a real interview.
  - Include `related_concepts` so the candidate can navigate to adjacent lessons.
- Use the same OpenAI client pattern as the existing `InterviewGenerator` and `InterviewEvaluator`.

**Verification:**
- Generate a lesson for "React useEffect cleanup function" with context "frontend interview question about memory leaks".
- Verify the JSON contains all required sections, an interactive code example, and an interview angle section.
- Verify the code example is in JavaScript (matching the JD context).

---

### Step 8.2 — Lesson Generator Module

**Objective:** Add lesson generation capability to `cv_optimizer/interview.py`.

**Tasks:**
- Add a `generate_lesson()` function or method to `cv_optimizer/interview.py`:
  ```python
  def generate_lesson(concept: str, context: str = "", session_id: int = None, app_id: int = None) -> dict:
  ```
- Flow:
  1. If `session_id` is provided, pull the JD and Master CV for richer context.
  2. Build the user prompt: the concept, context, relevant JD technologies, and related strengths/weaknesses from the evaluation.
  3. Call the LLM with the `lesson-generator.md` prompt.
  4. Parse the JSON response.
  5. Insert the lesson into the `lessons` table.
  6. Return `{ "lesson_id": id, "lesson": content }`.
- Deduplication: if a lesson with the same `concept` already exists for the same `application_id`, return the existing one (to avoid regenerating the same lesson on repeated clicks).

**Verification:**
- Generate a lesson programmatically, verify it's stored in the DB with all fields populated.
- Generate the same concept twice for the same application, verify the second call returns the existing lesson.

---

### Step 8.3 — Lesson Template

**Objective:** Create the blog-like lesson HTML page.

**Tasks:**
- Create `templates/lesson.html` — a Jinja2 template that renders the lesson content.
- **Layout:**
  - **Header:** Title, difficulty badge, read time estimate, related concepts as tags.
  - **Content flow:** Each section rendered as a blog section with heading and body (Markdown-rendered or pre-formatted).
  - **Interactive code section:** Two-pane layout — left pane is a Monaco Editor with the `starter_code` (editable), right pane shows `expected_output` in a styled `<pre>` block. Below both: an "Explain Solution" toggle that reveals the `solution_code` in a readonly Monaco editor and the LLM's `explanation` text.
  - **Chart section:** Renders a `<canvas>` element with Chart.js, initialized from the `chart_config` JSON. Dark-theme compatible colors included in the LLM-generated config. Caption displayed below.
  - **Diagram section:** Renders a Mermaid diagram from the `diagram_code` string. Mermaid auto-renders on page load when the `.mermaid` class is present. Caption displayed below.
  - **Interactive widget section:** Renders HTML form controls (range sliders, toggles, selects) from the `controls` array. Each output uses the JavaScript `Function` constructor to evaluate the `compute` expression reactively — every control change triggers recalculation. Outputs update in real time. Styled as a bordered "Experiment" card with a distinct background.
  - **Related concepts:** Clickable tags at the bottom that navigate to `/api/learn/generate?concept=X`.
- **Styling:** Dark theme matching the interview UI. Blog-article typography (serif or clean sans-serif, generous line-height, comfortable reading width ~700px). Interactive section breaks out of the narrow column into full-width code panes.
- Use the existing Monaco AMD loader pattern from `interview.html` (already in `<head>`).
- Load Chart.js via CDN: `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>` — single script tag, no bundler needed.
- Load Mermaid via CDN: `<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>` — initialize with `mermaid.initialize({ startOnLoad: true, theme: 'dark' })`.

**Verification:**
- Render a lesson page with a real lesson JSON. Verify all sections appear.
- Verify the Monaco Editor loads with the starter code, is editable, and the "Explain Solution" toggle reveals the solution.
- Verify related concept tags are clickable and navigate to generate new lessons.

---

### Step 8.4 — Server Routes

**Objective:** Add lesson routes to `server.py`.

**Tasks:**

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/learn/generate` | Generate a lesson for a concept. Body: `{ "concept": "...", "context": "...", "session_id": null, "app_id": null }` |
| `GET` | `/learn/{lesson_id}` | Serve the lesson HTML page |
| `GET` | `/api/learn/{lesson_id}` | Return the lesson as JSON (for client-side rendering or API access) |
| `GET` | `/learn` | Lesson library — list all generated lessons (HTML page) |

**`POST /api/learn/generate`** flow:
1. Accept JSON body with `concept` (required), `context` (optional), `session_id` (optional), `app_id` (optional).
2. Call `generate_lesson(concept, context, session_id, app_id)`.
3. Return `{ "lesson_id": id, "url": f"http://localhost:8000/learn/{id}" }`.

**`GET /learn/{lesson_id}`** flow:
1. Load lesson from DB.
2. Render `lesson.html` template with the lesson content.

**`GET /learn`** flow:
1. List all lessons from DB, ordered by `created_at DESC`.
2. Render a library page showing lesson cards (title, concept, difficulty, read time, linked concepts).

**Verification:**
- POST a concept to generate a lesson, verify 200 with a valid URL.
- Open the returned URL, verify the lesson page renders.
- Open `/learn`, verify the library lists all generated lessons.

---

### Step 8.5 — Hint Panel Integration

**Objective:** Add "Deep Dive →" links to the interview hint panel so candidates can jump to a full lesson from within a mock session.

**Tasks:**
- In `templates/interview.html`:
  - In the hint box (`#hint-box`), below the concept tags, add a link:
    ```html
    <a href="#" class="deep-dive-link" id="hint-deep-dive" style="display:none;">
      Deep Dive: Learn more about <span id="hint-concept-name"></span> →
    </a>
    ```
  - When a hint is shown, use the hint's `expected_concepts` to populate the link.
  - On click, the first expected concept becomes the target: POST `/api/learn/generate` with that concept, then navigate to the lesson page.
- In `static/interview.js`:
  - When `renderQuestion()` shows the hint, set the `#hint-concept-name` text to `q.expected_concepts[0]` and show the deep dive link.
  - On click, generate the lesson (with a loading state on the link) and navigate.

**Why from the hint, not just after evaluation?**
Software engineers often learn by doing. When a candidate sees a hint during the mock session and realizes they didn't know the concept, that's the moment of highest motivation — they want to understand *now*, not after the session ends. The deep dive link captures that momentum.

**Verification:**
- During a mock interview, click "Show Hint" on a question. Verify the "Deep Dive →" link appears with the first expected concept name.
- Click the link. Verify it generates a lesson and opens it in the same tab.
- After viewing the lesson, press back (or Cmd+←) to return to the interview session. Verify answers are preserved.

---

### Step 8.6 — Evaluation Report Integration

**Objective:** Add "Deep Dive →" links to each weakness in the evaluation report so candidates can directly study what they missed.

**Tasks:**
- In `templates/interview_report.html`:
  - For each `weakness` entry in the evaluation, add a "Deep Dive →" link:
    ```html
    <a href="/api/learn/generate?concept={{ weakness | urlencode }}&session_id={{ session_id }}">
      Deep Dive →
    </a>
    ```
  - The link opens a new tab (so the report stays visible).
- The concept name is extracted from the weakness string (e.g., "Did not address idempotency" → concept = "idempotency in distributed systems", which the LLM maps to a full lesson).
- Since the weakness text is free-form, the server endpoint handles fuzzy concept resolution: the LLM maps the weakness description to a canonical concept name before generating the lesson.

**Verification:**
- Complete an interview evaluation. Verify each weakness has a "Deep Dive →" link.
- Click a link. Verify a new tab opens with the generated lesson.
- Verify the lesson's concept accurately reflects the weakness.

---

### Step 8.7 — TUI Lesson Library

**Objective:** Add a lesson library accessible from the TUI dashboard, allowing the candidate to browse all generated lessons.

**Tasks:**
- In `cv_optimizer/tui/app.py`:
  - Add keybinding `L` — "Lessons" — that opens the lesson library in the browser:
    ```python
    webbrowser.open("http://localhost:8000/learn")
    ```
  - Implementation mirrors the `action_sankey` pattern — calls `webbrowser.open` directly (no server-side work needed).
- Add `db.list_lessons()` for database queries (useful if we later build a TUI-native lesson browser).
- Update footer binding hints to include `[L]essons`.

**Verification:**
- Press `L` in the TUI. Verify the browser opens to `/learn` showing the lesson library.
- Verify lessons generated from evaluations appear in the library.
- Verify lessons generated from hints appear in the library.

---

### Step 8.8 — Lesson Frontend Logic

**Objective:** Create the JavaScript logic for interactive lesson features (Monaco editors, Chart.js graphs, Mermaid diagrams, and reactive widgets).

**Tasks:**
- Create `static/lesson.js`.
- **Monaco initialization:** For each interactive code section in the lesson (identified by `type: "interactive"` in the JSON data), create a Monaco editor with the `starter_code`.
- **Chart.js initialization:** For each section with `type: "chart"`, create a `<canvas>` element and initialize a `new Chart(ctx, {type, data: chart_config, options: chart_options})` using the LLM-generated config. Charts use the dark theme color palette.
- **Mermaid initialization:** For each section with `type: "diagram"`, render the `diagram_code` into a `<pre class="mermaid">` block. Mermaid's `startOnLoad: true` auto-renders it. Wrap in a container with `class="mermaid"` for the library to detect.
- **Interactive widgets:** For each section with `type: "interactive_widget"`:
  1. Render HTML controls from the `controls` array (range inputs with `<input type="range">`, toggles with `<input type="checkbox">`).
  2. Render output displays from the `outputs` array (styled value cards).
  3. Create a `recompute()` function that gets current control values, passes them into each output's `compute` expression via `new Function(...)`, and updates the DOM.
  4. Attach `input` and `change` event listeners to every control that call `recompute()`.
  5. Recompute on first render to show default values.
- **Solution toggle:** A button "Show Solution" that, when clicked: reveals a second readonly Monaco editor with the `solution_code`, reveals the `explanation` text below, button text changes to "Hide Solution".
- **Related concepts:** Each tag in the related concepts section is a link to `/api/learn/generate?concept=X` (generates on-the-fly and redirects).
- **Responsive layout:** Code panes and chart+diagram sections use full width. Widget controls stack vertically on narrow screens.

**Verification:**
- Open a lesson with an interactive section. Verify the Monaco Editor loads with starter code and is editable.
- Click "Show Solution". Verify the solution editor and explanation appear.
- Click "Hide Solution". Verify they disappear.
- Verify related concept links generate and navigate to new lessons.

---

## Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Blog-like tone, not textbook** | The candidate is already in "interview prep" mode. A blog-like tutorial (accessible, conversational, practical) fits the mindset better than an academic reference. The LLM is instructed to write like a senior engineer writing a dev blog post. |
| 2 | **Rich media mix per lesson** | Each lesson includes at most one code example (Monaco), one chart (Chart.js), one diagram (Mermaid), and one interactive widget. This gives the candidate multiple ways to engage with the concept without overwhelming the page with heavy JS. The LLM decides which types fit the concept. |
| 3 | **Trigger from both hint and evaluation** | The hint trigger captures in-the-moment curiosity ("I don't know this — teach me now"). The evaluation trigger captures post-mortem study ("I missed this — let me fix it before the real interview"). Both are valid learning moments. |
| 4 | **Deduplication by concept + app** | Regenerating the same lesson on every click wastes LLM tokens and time. Lessons are keyed by concept + application_id. If a candidate clicks "Deep Dive: idempotency" twice for the same application, they get the existing lesson. |
| 5 | **Flat, not nested lesson structure** | Lessons are independent, not part of a course tree. The candidate follows their own learning path via related concepts — like Wikipedia, not a syllabus. This matches the organic, just-in-time nature of interview prep. |
| 6 | **Generated content, not curated** | Every lesson is LLM-generated on demand. No hand-written content, no content database. This means lessons are always tailored to the candidate's specific technologies and job applications, and the library grows organically as they encounter new concepts. |
| 7 | **No code execution** | Same constraint as Milestone 7. The LLM evaluates code through reasoning, not a sandbox. The "expected output" is text that describes what the correct code should produce — it's a learning aid, not an auto-grader. |
| 8 | **CDN-loaded libraries only** | Monaco Editor (AMD), Chart.js, and Mermaid are all loaded via CDN <script> tags. No npm, no webpack, no build step. This keeps the project dependency-free at the JS level while still delivering rich, interactive visual content. |

---

## UI/UX Specifications

### Lesson Page Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  ← Back to Interview                              [Difficulty]   │
│                                                  [5 min read]    │
│  # Understanding Idempotency                                      │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                                                              │ │
│  │  (Body text — narrow column, blog typography, ~680px max)    │ │
│  │                                                              │ │
│  │  Idempotency means that performing the same operation        │ │
│  │  multiple times produces the same result...                  │ │
│  │                                                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ## Why It Matters in Interviews                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Body text...                                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ## Try It Yourself                                               │
│  ┌────────────────────────────┬────────────────────────────────┐ │
│  │  Your Code (editable)      │  Expected Output               │ │
│  │  ┌──────────────────────┐  │  ┌──────────────────────────┐  │ │
│  │  │ fn process(msg) {    │  │  │ ✓ msg-1 processed        │  │ │
│  │  │  // ...              │  │  │ ✓ msg-2 processed        │  │ │
│  │  │ }                    │  │  │ ✗ msg-1 duplicate, skip  │  │ │
│  │  └──────────────────────┘  │  └──────────────────────────┘  │ │
│  │                            │                                  │ │
│  │  [Show Solution]           │                                  │ │
│  └────────────────────────────┴────────────────────────────────┘ │
│                                                                   │
│  ## Message Throughput vs Duplicate Rate                           │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  [Chart.js line chart — two lines, dark theme]              │ │
│  │                                                              │ │
│  │  Duplicate Messages                                          │ │
│  │  220 ┤                              ╭── With (red)           │ │
│  │  150 ┤                         ╭───╯                        │ │
│  │  100 ┤                   ╭─────╯                             │ │
│  │   50 ┤             ╭─────╯                                   │ │
│  │    0 ┤─────╯ (green) With Idempotency                       │ │
│  │      └───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───      │ │
│  │       10  100  500  1000  5000  msg/s                        │ │
│  │                                                              │ │
│  │  Higher throughput amplifies the duplicate problem...        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ## At-Least-Once vs Exactly-Once Delivery                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  [Mermaid sequence diagram]                                  │ │
│  │  Producer → Broker → Consumer → ACK → Re-deliver → Dedup    │ │
│  │                                                              │ │
│  │  Sequence diagram showing how idempotent consumers...        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ## Experiment: Throttle vs Queue Backlog                          │
│  ┌─────────────────────────── Experiment ──────────────────────┐ │
│  │  Consumer Throttle  ──────●──────────────  100 msg/s         │ │
│  │  Producer Rate      ────────────●────────  500 msg/s         │ │
│  │  Idempotency        [ ON ◼ ]                                │ │
│  │                                                              │ │
│  │  ┌──────────────────┐  ┌──────────────────┐                 │ │
│  │  │ Queue Backlog    │  │ Duplicates/Hour  │                 │ │
│  │  │ 200 messages     │  │ 0                │                 │ │
│  │  └──────────────────┘  └──────────────────┘                 │ │
│  │                                                              │ │
│  │  Even with low throttle... duplicates drop to zero.          │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ## Common Pitfalls                                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Body text...                                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ## Interview Angle                                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Body text...                                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Related: [message durability] [dead-letter queues] [exactly-once]│
└──────────────────────────────────────────────────────────────────┘
```

### Solution Toggle

```
Before:
  [Show Solution]

After:
  ┌──────────────────────────────────────────────────────────────┐
  │  Solution (readonly)                                          │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │ const processed = new Set();                            │  │
  │  │ function handleMessage(msg) {                           │  │
  │  │   if (processed.has(msg.id)) {                          │  │
  │  │     console.log('Skipping duplicate:', msg.id);         │  │
  │  │     return;                                             │  │
  │  │   }                                                     │  │
  │  │   processed.add(msg.id);                                │  │
  │  │   console.log('Processing:', msg.id);                   │  │
  │  │ }                                                       │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                                │
  │  The Set data structure provides O(1) lookup. We check        │
  │  before processing and skip if already seen...                 │
  └──────────────────────────────────────────────────────────────┘
  [Hide Solution]
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM generates incorrect or misleading lesson content | Candidate learns wrong concepts | The interview angle section ties back to real interview expectations. Lessons are scoped to concepts the candidate actually encountered (from JD), not random topics. Candidate can cross-reference with external sources. |
| Lesson generation is slow (LLM latency) | Candidate loses momentum when clicking "Deep Dive" during an interview session | The link opens in the same tab with a spinner overlay. The candidate can optionally open in a new tab and continue the interview. Deduplication means repeat clicks are instant. |
| Lessons accumulate and never cleaned | DB grows unboundedly | Lessons are small (JSON text, ~5-10 KB each). Even 100 lessons is <1 MB. If needed, add a "prune old lessons" command later. |
| Multiple Monaco instances on one page | Page performance degrades | Only the interactive section gets Monaco. The solution is also Monaco but readonly (lighter weight). At most 2 editors per page. |
| Chart.js or Mermaid CDN unavailable | Charts/diagrams render as empty containers | The lesson page detects `typeof Chart === 'undefined'` and falls back to showing the raw chart_config JSON in a styled `<pre>`. Mermaid blocks render as plain text if the library fails to load. The text content of the lesson (headings, body, interview angle) is unaffected. |

---

## Integration Touchpoints

| From | To | Action |
|------|----|--------|
| Interview hint panel | Lesson page | "Deep Dive →" link, same tab |
| Evaluation report weakness | Lesson page | "Deep Dive →" link, new tab |
| TUI dashboard | Lesson library | `[L]` keybinding → `/learn` |
| Lesson page "Related" tags | New lesson | Auto-generate and redirect |
