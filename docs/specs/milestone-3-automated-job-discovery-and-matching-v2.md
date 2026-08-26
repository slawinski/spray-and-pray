# Spray and Pray — Automated Job Discovery, Matching & Draft Import Specification

**Suggested file:** `docs/specs/milestone-3-automated-job-discovery-and-matching-v2.md`

**Status:** Implementation-ready  
**Milestone:** 3 v2  
**Supersedes:** `docs/specs/milestone-3-automated-job-discovery-and-scraping.md`  
**Depends on:** existing Match Score implementation  
**Primary threshold:** `85`  
**Default behavior:** discover → score → create Draft; **do not generate CV or cover letter automatically**

---

# 1. Executive Summary

Spray and Pray currently begins its workflow after the user has already found a job. The browser extension or local JD is fed into the application tracker, which creates an application, calculates a match score, generates a tailored CV, optionally generates a cover letter, and inserts the application into the existing state machine.

This milestone moves job discovery into Spray and Pray itself.

The application SHALL periodically discover active frontend and frontend-leaning full-stack roles, normalize them into a canonical job representation, reject obviously incompatible jobs without spending LLM tokens, deduplicate repeated listings, calculate the existing candidate↔JD Match Score, and automatically create application Drafts for jobs whose score is at least the configured threshold.

The target end-to-end flow is:

```text
JOB SOURCES
    │
    ├── Google Jobs / aggregator
    ├── Greenhouse
    ├── Lever
    └── Ashby
    │
    ▼
NORMALIZE
    │
    ▼
CANONICAL JOB POSTING
    │
    ▼
DEDUPE / UPSERT
    │
    ▼
CHEAP ELIGIBILITY PREFILTER
    │
    ├── incompatible ───────────────▶ filtered
    │
    └── compatible / ambiguous
                │
                ▼
          MATCH SCORE v2
                │
        ┌───────┴────────┐
        │                │
      < 85             >= 85
        │                │
        ▼                ▼
     retain        CREATE APPLICATION
   as posting            │
                         ▼
                       DRAFT
                         │
                 CV = not generated
                 CL = not generated
                         │
                         ▼
                       TUI
```

The important architectural rule is:

> **A discovered job is not automatically an application.**

A job may exist in Spray and Pray's discovery database at 62%, 78%, or 84% without appearing in the application funnel.

Only a qualifying job becomes an application.

Likewise:

> **A qualifying discovered job becomes a Draft, not an Applied application.**

No submission has occurred yet, and the existing application state machine must remain truthful.

---

# 2. Goals

The implementation SHALL:

1. discover newly posted frontend and frontend-leaning full-stack jobs automatically;
2. support Warsaw office/hybrid jobs;
3. support remote jobs that may legally/practically be performed from Poland;
4. include Mid and Senior roles;
5. search by role and capability rather than by one specific frontend framework;
6. treat mainstream JavaScript frontend frameworks as highly transferable;
7. retain meaningful penalties for genuinely framework-specific requirements;
8. calculate Match Score before creating an application;
9. automatically create Draft applications for active jobs scoring `>= 85`;
10. avoid duplicate applications;
11. avoid repeatedly scoring an unchanged JD;
12. avoid generating CVs/cover letters for jobs the user has not reviewed;
13. expose discovery metadata and Match Score in the TUI;
14. support manual discovery from the CLI/TUI;
15. support scheduled unattended discovery;
16. isolate failures by source so one broken provider does not stop the entire run;
17. preserve the existing manual/browser-extension workflow.

---

# 3. Non-Goals

This milestone SHALL NOT implement:

- automatic submission to employer ATS forms;
- answering screening questions;
- automated salary-expectation answers;
- CAPTCHA bypassing;
- browser automation against LinkedIn;
- login/session automation against protected job boards;
- fabricated candidate information;
- modification of `master_cv.json`;
- fully autonomous CV/cover-letter generation by default;
- automatic transition from `draft` to `applied`;
- exhaustive crawling of the entire public web;
- machine-learned scoring weights;
- framework-specific résumé fabrication;
- application decisions based only on compensation.

Automated submission remains a later milestone.

---

# 4. Verified Current-State Constraints

The current Match Score implementation already has the correct core philosophy:

- `master_cv.json` is the candidate source of truth;
- tailored CVs are not scoring inputs;
- the LLM extracts/maps requirements;
- deterministic Python owns the numeric score;
- positive evidence must point back to actual Master CV data.

The current score defines `85+` as `STRONG`.

However, `MatchService.score_application()` currently requires an existing application ID and JD file.

The discovery feature therefore requires Match Score to be refactored so that **a raw JD can be scored before an application exists**.

The current `track()` workflow creates an application, copies its JD, runs Match Score, and then immediately proceeds into CV optimization/PDF generation.

For that reason, discovery SHALL NOT call:

```text
POST /api/track
```

for every discovered job.

The previous Milestone 3 spec proposed doing exactly that. That behavior is now superseded.

---

# 5. Architectural Principles

## 5.1 Separate jobs from applications

A `job_posting` represents:

> A vacancy Spray and Pray knows exists.

An `application` represents:

> A vacancy the user has decided to pursue.

These concepts MUST have separate persistence models.

---

## 5.2 Filter before LLM scoring

The system should not spend an LLM request on:

- internships;
- explicitly Junior roles;
- backend-only Python jobs;
- US-only remote jobs;
- office-only jobs in another country;
- empty JDs;
- duplicate postings already scored.

The sequence MUST be:

```text
fetch
→ normalize
→ dedupe
→ prefilter
→ LLM match
```

not:

```text
fetch
→ LLM everything
→ filter
```

---

## 5.3 Search by role, not framework

The discovery system MUST NOT primarily search for:

```text
React Developer
Next.js Developer
```

Doing so recreates the bias this milestone is intended to eliminate.

Preferred search concepts:

```text
Frontend Engineer
Frontend Developer
Senior Frontend Engineer
Product Engineer
Software Engineer Frontend
Full Stack Engineer JavaScript
Full Stack Engineer TypeScript
UI Engineer
Web Engineer
```

Framework names may be used to broaden individual searches but MUST NOT define the candidate universe.

---

## 5.4 Framework identity is a soft compatibility signal

Mainstream JavaScript frontend frameworks are considered members of the same transferable capability family.

Examples include:

```text
React
Next.js
Preact

Vue
Nuxt

Angular

Svelte
SvelteKit

Solid
SolidStart

Ember

Qwik

Lit
```

The implementation MUST distinguish:

```text
"We use Angular"
```

from:

```text
"6+ years of production Angular required,
deep RxJS + NgRx knowledge,
expert Angular change-detection knowledge"
```

The former is a very small gap.

The latter is a meaningful specialization gap.

---

# 6. Proposed Package Structure

Add:

```text
cv_optimizer/
├── discovery/
│   ├── __init__.py
│   ├── models.py
│   ├── config.py
│   ├── service.py
│   ├── filters.py
│   ├── dedupe.py
│   ├── activity.py
│   ├── importer.py
│   └── sources/
│       ├── __init__.py
│       ├── base.py
│       ├── serpapi.py
│       ├── greenhouse.py
│       ├── lever.py
│       └── ashby.py
│
├── matching.py
├── framework_transfer.py
├── tracker.py
├── db.py
└── tui/
    └── app.py
```

Add tests:

```text
tests/
├── fixtures/
│   └── jobs/
│       ├── serpapi.json
│       ├── greenhouse.json
│       ├── lever.json
│       └── ashby.json
│
├── test_discovery_models.py
├── test_discovery_filters.py
├── test_discovery_dedupe.py
├── test_discovery_sources.py
├── test_discovery_importer.py
├── test_discovery_integration.py
└── test_framework_transferability.py
```

---

# 7. Discovery Configuration

Do not introduce YAML solely for this feature.

The current project is lightweight and already uses Python/Pydantic/JSON extensively. Use JSON plus environment variables for secrets.

Add:

```text
job_search.example.json
```

and gitignore:

```text
job_search.json
```

Example:

```json
{
  "enabled": true,
  "minimum_match_score": 85,
  "max_post_age_days": 30,
  "max_scores_per_run": 30,

  "roles": [
    "frontend engineer",
    "frontend developer",
    "product engineer",
    "software engineer frontend",
    "full stack engineer javascript",
    "full stack engineer typescript",
    "web engineer",
    "ui engineer"
  ],

  "seniority": {
    "include": ["mid", "senior"],
    "include_unleveled": true,
    "include_staff": false,
    "include_lead": false
  },

  "locations": {
    "warsaw": {
      "onsite": true,
      "hybrid": true
    },
    "remote": {
      "poland": true,
      "europe": true,
      "emea": true,
      "worldwide": true
    }
  },

  "framework_policy": "transferable_js",

  "priorities": {
    "javascript_typescript": "high",
    "product_engineering": "high",
    "design_systems": "high",
    "accessibility": "high",
    "data_visualization": "high",
    "realtime_interfaces": "high",
    "ux_collaboration": "high",
    "nodejs": "medium",
    "ai_products": "medium",
    "mentoring": "medium"
  },

  "auto_import": true,

  "generation": {
    "auto_generate_cv": false,
    "auto_generate_cover_letter": false,
    "auto_generate_cv_min_score": null
  },

  "sources": {
    "serpapi": {
      "enabled": true,
      "max_pages_per_query": 2
    },
    "greenhouse": {
      "enabled": true,
      "boards": []
    },
    "lever": {
      "enabled": true,
      "sites": []
    },
    "ashby": {
      "enabled": true,
      "boards": []
    }
  }
}
```

Secrets belong in `.env`:

```text
SERPAPI_API_KEY=...
```

Never write the API key into `job_search.json`.

---

# 8. Source Strategy

## 8.1 Source interface

Every source adapter MUST implement the same contract.

```python
class JobSource(Protocol):
    name: str

    def fetch(
        self,
        query: DiscoveryQuery,
    ) -> list[DiscoveredJob]:
        ...
```

Source failures MUST be isolated.

Example:

```python
for source in sources:
    try:
        jobs = source.fetch(query)
    except Exception:
        logger.exception("Discovery source failed: %s", source.name)
        continue
```

One broken source MUST NOT fail the discovery run.

---

# 9. Primary Broad Discovery Source — Google Jobs via SerpApi

SerpApi exposes structured Google Jobs results, requires a query, supports geographic search, and paginates using `next_page_token`.

Use it as the initial broad-market source because direct ATS APIs only expose jobs from employers whose boards are already known.

Endpoint:

```text
GET https://serpapi.com/search
```

Parameters:

```text
engine=google_jobs
q=<role search>
location=<location>
hl=en
api_key=<secret>
```

Example conceptual searches:

```text
"frontend engineer"
location="Warsaw, Poland"

"frontend developer remote Europe"

"product engineer TypeScript remote"

"software engineer frontend remote Poland"

"full stack engineer TypeScript remote Europe"
```

Do NOT generate one request per frontend framework.

That would disproportionately weight React and create unnecessary duplicate results.

Pagination SHALL stop when:

- no `next_page_token` exists;
- `max_pages_per_query` is reached;
- the per-run global fetch cap is reached.

---

# 10. ATS Sources

ATS sources serve two purposes:

1. find jobs from explicitly tracked companies;
2. provide high-confidence active-state verification.

## 10.1 Lever

Lever exposes published postings through its public postings API and can return JSON. Published postings are publicly visible.

Adapter form:

```text
https://api.lever.co/v0/postings/{site}?mode=json
```

Normalized fields should include:

```text
id
text/title
categories.location
categories.commitment
hostedUrl
applyUrl
description
```

---

## 10.2 Ashby

Ashby exposes currently published job postings via its public Job Posting API and can optionally return compensation.

Adapter form:

```text
GET https://api.ashbyhq.com/posting-api/job-board/{board}
    ?includeCompensation=true
```

Useful normalized fields include:

```text
title
location
secondaryLocations
isRemote
workplaceType
descriptionPlain
publishedAt
employmentType
jobUrl
applyUrl
compensation
```

---

## 10.3 Greenhouse

Implement a Greenhouse adapter behind the same source interface.

The adapter MUST accept configured board identifiers and return only public postings.

Do not make Greenhouse support a prerequisite for shipping the first working discovery loop.

Recommended implementation order:

```text
SerpApi
→ Lever
→ Ashby
→ Greenhouse
```

---

# 11. Normalized Job Model

Create `cv_optimizer/discovery/models.py`.

```python
class DiscoveredJob(BaseModel):
    source: str
    external_id: str

    company: str
    role: str
    description: str

    source_url: str | None = None
    apply_url: str | None = None
    canonical_url: str | None = None

    location_text: str | None = None

    work_model: Literal[
        "onsite",
        "hybrid",
        "remote",
        "unknown",
    ] = "unknown"

    remote_scope: Literal[
        "poland",
        "europe",
        "eu",
        "eea",
        "emea",
        "worldwide",
        "country_specific",
        "unknown",
    ] = "unknown"

    seniority: Literal[
        "intern",
        "junior",
        "mid",
        "senior",
        "staff",
        "lead",
        "principal",
        "unknown",
    ] = "unknown"

    employment_type: str | None = None

    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_raw: str | None = None

    posted_at: datetime | None = None
    source_updated_at: datetime | None = None

    active_state: Literal[
        "active",
        "inactive",
        "unknown",
    ] = "unknown"

    active_confidence: Literal[
        "high",
        "medium",
        "low",
    ] = "low"

    raw_payload: dict | None = None
```

The matcher SHALL consume:

```text
description
```

not the raw source payload.

---

# 12. Database Design

## 12.1 Do not expand `applications` for discovery metadata

Current DB access uses:

```python
SELECT * FROM applications
```

and code destructures the tuple by position.

Therefore this milestone SHOULD NOT add discovery-specific columns directly to `applications`.

Instead create independent tables.

---

# 13. `job_postings`

Add:

```sql
CREATE TABLE IF NOT EXISTS job_postings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    company             TEXT NOT NULL,
    role                TEXT NOT NULL,
    description         TEXT NOT NULL,
    description_hash    TEXT NOT NULL,

    canonical_url       TEXT,

    location_text       TEXT,
    work_model          TEXT NOT NULL DEFAULT 'unknown',
    remote_scope        TEXT NOT NULL DEFAULT 'unknown',
    seniority           TEXT NOT NULL DEFAULT 'unknown',
    employment_type     TEXT,

    salary_min          REAL,
    salary_max          REAL,
    salary_currency     TEXT,
    salary_period       TEXT,
    salary_raw          TEXT,

    posted_at           DATETIME,
    first_seen_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    active_state        TEXT NOT NULL DEFAULT 'unknown',
    active_confidence   TEXT NOT NULL DEFAULT 'low',

    prefilter_state     TEXT NOT NULL DEFAULT 'pending',
    prefilter_reason    TEXT,

    match_state         TEXT NOT NULL DEFAULT 'pending',
    latest_match_score  INTEGER,
    latest_match_label  TEXT,

    user_state          TEXT NOT NULL DEFAULT 'pending',

    application_id      INTEGER UNIQUE,
    imported_at         DATETIME,
    dismissed_at        DATETIME,

    FOREIGN KEY(application_id)
        REFERENCES applications(id)
        ON DELETE SET NULL
);
```

Allowed `user_state` values:

```text
pending
imported
dismissed
```

Do not overload `active_state` with user actions.

---

# 14. `job_source_refs`

The same underlying vacancy may appear through:

```text
Google Jobs
+
company Greenhouse board
+
another aggregator
```

Do not represent these as three canonical jobs.

Add:

```sql
CREATE TABLE IF NOT EXISTS job_source_refs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_posting_id  INTEGER NOT NULL,

    source          TEXT NOT NULL,
    external_id     TEXT NOT NULL,

    source_url      TEXT,
    apply_url       TEXT,

    raw_json        TEXT,

    first_seen_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    active_state    TEXT NOT NULL DEFAULT 'unknown',

    FOREIGN KEY(job_posting_id)
        REFERENCES job_postings(id)
        ON DELETE CASCADE,

    UNIQUE(source, external_id)
);
```

Index:

```sql
CREATE INDEX IF NOT EXISTS idx_job_source_refs_job
ON job_source_refs(job_posting_id);
```

---

# 15. `job_match_assessments`

Match Score currently belongs to an `application_id`.

Discovery needs the same score before an application exists.

Add:

```sql
CREATE TABLE IF NOT EXISTS job_match_assessments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_posting_id      INTEGER NOT NULL,

    score               INTEGER NOT NULL
                        CHECK(score >= 0 AND score <= 100),

    label               TEXT NOT NULL,
    confidence          TEXT NOT NULL,
    base_score          REAL NOT NULL,

    assessment_json     TEXT NOT NULL,

    candidate_hash      TEXT NOT NULL,
    jd_hash             TEXT NOT NULL,

    scoring_version     TEXT NOT NULL,
    prompt_version      TEXT NOT NULL,
    model_name          TEXT NOT NULL,

    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(job_posting_id)
        REFERENCES job_postings(id)
        ON DELETE CASCADE
);
```

Indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_job_match_job
ON job_match_assessments(job_posting_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_job_match_cache
ON job_match_assessments(
    job_posting_id,
    candidate_hash,
    jd_hash,
    scoring_version,
    prompt_version,
    model_name
);
```

---

# 16. `discovery_runs`

Add run-level observability:

```sql
CREATE TABLE IF NOT EXISTS discovery_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    started_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at        DATETIME,

    status              TEXT NOT NULL DEFAULT 'running',

    fetched_count       INTEGER NOT NULL DEFAULT 0,
    normalized_count    INTEGER NOT NULL DEFAULT 0,
    new_count           INTEGER NOT NULL DEFAULT 0,
    updated_count       INTEGER NOT NULL DEFAULT 0,
    filtered_count      INTEGER NOT NULL DEFAULT 0,
    scored_count        INTEGER NOT NULL DEFAULT 0,
    qualified_count     INTEGER NOT NULL DEFAULT 0,
    imported_count      INTEGER NOT NULL DEFAULT 0,

    source_stats_json   TEXT,
    errors_json         TEXT
);
```

Possible statuses:

```text
running
completed
completed_with_errors
failed
```

---

# 17. Deduplication

Deduplication MUST happen before LLM scoring.

Use multiple increasingly fuzzy levels.

## 17.1 Level 1 — exact provider identity

```text
source + external_id
```

If found:

```text
update last_seen_at
update source ref
update active state
```

Do not create another canonical posting.

---

## 17.2 Level 2 — normalized canonical URL

Normalize URLs by:

- lowercasing hostname;
- removing fragments;
- removing known tracking parameters;
- removing `utm_*`;
- removing `gh_src`;
- removing irrelevant query ordering;
- normalizing trailing slash.

Do not remove identifiers that distinguish jobs.

---

## 17.3 Level 3 — cross-source fingerprint

Generate:

```text
normalized company
+
normalized title
+
normalized location
```

Example normalization:

```text
"Senior Front-End Engineer"
→ "senior frontend engineer"

"N-iX"
→ "n ix"
```

Then compare description hashes.

Exact normalized company/title/location with highly similar descriptions should merge.

---

## 17.4 Do not over-dedupe

These are NOT necessarily duplicates:

```text
Senior Frontend Engineer — Warsaw
Senior Frontend Engineer — Kraków
```

or:

```text
Frontend Engineer, Payments
Frontend Engineer, Growth
```

even at the same company.

When uncertain, preserve two postings rather than merge distinct vacancies.

---

# 18. Job Description Hashing

Reuse the existing JD normalization/hash logic wherever possible.

The canonical posting stores:

```text
description_hash
```

If:

```text
old_hash == new_hash
```

and the candidate/scoring identity is unchanged:

```text
do not rerun the LLM
```

If:

```text
old_hash != new_hash
```

then:

```text
match_state = pending
```

and the job becomes eligible for re-scoring.

---

# 19. Cheap Prefilter

Create:

```text
cv_optimizer/discovery/filters.py
```

Return:

```python
class PrefilterResult(BaseModel):
    state: Literal["pass", "fail", "review"]
    reason: str
```

`review` means:

> information is ambiguous; do not reject the job.

---

# 20. Role Filtering

## FAIL

Reject obvious:

```text
Intern Frontend Developer
Junior Frontend Engineer

Backend Python Developer
Java Backend Engineer
Data Engineer
Data Scientist
DevOps Engineer
QA Engineer
iOS Developer
Android Developer

Engineering Manager
Product Manager
Designer
```

unless future configuration explicitly enables those families.

---

## PASS

Examples:

```text
Frontend Engineer
Senior Frontend Engineer
Frontend Developer
Web Engineer
UI Engineer
Product Engineer
Software Engineer — Frontend
Full Stack Engineer
Fullstack TypeScript Engineer
```

---

## REVIEW

Ambiguous:

```text
Software Engineer
Product Developer
Application Engineer
```

Inspect the JD before deciding.

If frontend/JavaScript work is a substantial component, continue.

---

# 21. Seniority Filtering

Default accepted levels:

```text
mid
senior
```

Unlevelled roles SHOULD be retained when the JD indicates appropriate experience/scope.

Examples:

```text
Frontend Engineer
5+ years experience
```

should not be rejected merely because `Senior` is absent from the title.

Default:

```text
staff = reject
lead = reject
principal = reject
```

unless enabled in config.

This can later be relaxed independently.

---

# 22. Geography Filtering

## Automatically PASS

```text
Warsaw — onsite
Warsaw — hybrid

Remote Poland

Remote Europe
Remote EU
Remote EEA
Remote EMEA

Worldwide remote
```

provided there is no explicit exclusion of Poland.

---

## Automatically FAIL

Examples:

```text
San Francisco onsite
London hybrid
Berlin onsite

Remote US only
Remote Canada only
Remote UK only
Remote Germany only

Must reside in California
Must be located in the United States
```

---

## REVIEW

Examples:

```text
Remote
Distributed
Work from anywhere in your region
Europe preferred
```

with no precise eligibility definition.

Ambiguity MUST NOT be interpreted as incompatibility.

The Match Score's existing eligibility machinery can later classify unresolved details.

---

# 23. Framework Filtering Rule

The prefilter MUST NEVER reject a job because it uses:

```text
Angular
Vue
Nuxt
Svelte
SvelteKit
Solid
Ember
```

instead of React.

Framework compatibility belongs in the Match Score.

---

# 24. Match Score Refactor

Current:

```python
MatchService.score_application(app_id)
```

is application-bound.

Refactor into a reusable underlying operation.

Target API:

```python
class MatchService:

    def assess_text(
        self,
        jd_text: str,
        *,
        master_cv_path: str | None = None,
    ) -> MatchResult:
        ...

    def score_application(
        self,
        app_id: int,
        *,
        force: bool = False,
        master_cv_path: str | None = None,
    ) -> dict:
        ...

    def score_job_posting(
        self,
        job_posting_id: int,
        *,
        force: bool = False,
        master_cv_path: str | None = None,
    ) -> dict:
        ...
```

Responsibilities:

```text
assess_text()
    load Master CV
    build match profile
    compute candidate hash
    compute JD hash
    call analyzer
    validate evidence
    deterministic scoring
    return result + identity metadata
```

Persistence is owned by the caller-specific wrapper.

```text
score_application()
→ match_assessments

score_job_posting()
→ job_match_assessments
```

Existing external behavior of `score_application()` MUST remain compatible.

---

# 25. Match Score v2 — Framework Transferability

The current Match Score explicitly says that a different framework is **not automatically a strong transfer** for a named mandatory framework.

That policy SHALL be superseded by `match-v2`.

Do not silently change historical `match-v1` semantics.

Set:

```text
MATCH_SCORING_VERSION=match-v2
MATCH_PROMPT_VERSION=prompt-v2
```

Historical rows remain valid historical assessments.

Their version identifiers allow them to coexist with new scores.

---

# 26. New Evidence Taxonomy

Current evidence values are:

```text
direct          1.00
strong_transfer 0.75
partial         0.40
unknown         0.50
none            0.00
```



Extend them to:

```python
EvidenceLevel = Literal[
    "direct",
    "framework_transfer",
    "strong_transfer",
    "framework_depth_gap",
    "partial",
    "none",
    "unknown",
]
```

Recommended values:

```python
EVIDENCE_VALUES = {
    "direct": 1.00,

    "framework_transfer": 0.92,

    "strong_transfer": 0.75,

    "framework_depth_gap": 0.60,

    "unknown": 0.50,

    "partial": 0.40,

    "none": 0.00,
}
```

And:

```python
_POSITIVE_EVIDENCE = (
    "direct",
    "framework_transfer",
    "strong_transfer",
    "framework_depth_gap",
    "partial",
)
```

A framework-transfer classification MUST still require real evidence pointers.

Example:

```json
{
  "requirement": "Angular",
  "evidence_level": "framework_transfer",
  "evidence_paths": [
    "/skills/frameworks_and_libraries/0",
    "/skills/frameworks_and_libraries/2",
    "/experience/1/achievements/0"
  ]
}
```

The evidence demonstrates substantial modern frontend framework experience.

It does **not** claim Angular experience that does not exist.

---

# 27. Framework Family

Add:

```text
cv_optimizer/framework_transfer.py
```

Example:

```python
JS_FRONTEND_FRAMEWORKS = {
    "react",
    "react.js",
    "next.js",
    "nextjs",
    "preact",

    "vue",
    "vue.js",
    "nuxt",
    "nuxt.js",

    "angular",

    "svelte",
    "sveltekit",

    "solid",
    "solidjs",
    "solid.js",

    "ember",
    "ember.js",

    "qwik",
    "lit"
}
```

Add aliases/normalization.

The LLM may identify the requirement, but Python SHOULD validate whether the named technology belongs to this family.

This prevents the model from deciding that arbitrary technologies are transferable merely because both are programming tools.

For example:

```text
React → Angular
```

may be framework transfer.

But:

```text
React → Django
React → Kubernetes
React → Terraform
```

is not.

---

# 28. Framework Scoring Rules

## Case A — exact experience

JD:

```text
React required
```

CV:

```text
React
```

Result:

```text
direct = 1.00
```

---

## Case B — framework named as implementation stack

JD:

```text
Our frontend uses Angular.
Experience with a modern frontend framework required.
```

Candidate has extensive React/Vue/Next experience.

Result:

```text
framework_transfer = 0.92
```

or `direct` against the normalized requirement:

```text
modern JavaScript frontend framework
```

depending on how requirements are deduplicated.

---

## Case C — named framework requirement, no deep specialization language

JD:

```text
Strong Angular experience.
```

No Angular in CV, but extensive React/Vue/TypeScript architecture.

Result:

```text
framework_transfer = 0.92
```

The JD is allowed to reduce the score slightly.

It MUST NOT cause an automatic `none`.

---

## Case D — deep framework-specific requirement

JD:

```text
6+ years commercial Angular
deep RxJS / NgRx expertise
expert understanding of Angular Signals
```

Candidate lacks Angular.

Represent requirements separately:

```text
Angular tenure
→ framework_depth_gap = 0.60

RxJS
→ none or partial based on actual CV

NgRx
→ none

Angular Signals
→ none
```

This job may naturally fall below 85.

That is intended.

---

## Case E — Svelte internals

JD:

```text
Expert Svelte 5
deep knowledge of runes/reactivity internals
```

Candidate has React/Vue but no Svelte.

Result:

```text
Svelte general framework experience
→ framework_depth_gap

Svelte runes
→ none
```

Again, the job receives a genuine penalty without treating the candidate as an inexperienced frontend engineer.

---

# 29. Hard-Gap Cap Interaction

Current scoring caps the final score at:

```text
69 if exactly one core MUST requirement = none
54 if two or more core MUST requirements = none
```



This behavior remains.

But:

```text
framework_transfer
framework_depth_gap
```

are NOT `none`.

Therefore:

```text
Angular requirement
+
credible mainstream frontend framework evidence
```

does not trigger the `69` hard cap by itself.

A genuinely absent independent requirement may still trigger the cap.

Example:

```text
React candidate applying to Angular role
→ no hard cap

Angular + mandatory Java backend experience
and candidate has no Java
→ Java may trigger hard cap
```

---

# 30. Match Prompt Changes

Update:

```text
cv_optimizer/prompts/match.md
```

Add explicit language:

```text
Mainstream JavaScript frontend frameworks are generally transferable.

Do not classify a requirement as "none" merely because the job uses a
different mainstream JavaScript frontend framework from the candidate's
proven production framework experience.

Use "framework_transfer" when:
- the requested technology is a mainstream JS frontend framework;
- the candidate has substantial production experience with one or more
  other mainstream JS frontend frameworks;
- the JD does not clearly require deep framework-specific tenure,
  internals, or companion ecosystem expertise.

Use "framework_depth_gap" when:
- exact framework depth is explicitly central to the role;
- the candidate has transferable frontend-framework expertise;
- but the exact depth requested is not evidenced.

Keep separate technologies separate.
Do not infer RxJS, NgRx, Angular Signals, Svelte runes, etc. merely from
general frontend experience.
```

The anti-hallucination rules remain unchanged.

---

# 31. Discovery Scoring Queue

After prefiltering, candidate jobs should be prioritized before LLM calls.

Recommended order:

```text
1. newest posted_at
2. active confidence
3. role relevance
4. Warsaw / Poland / Europe eligibility certainty
5. previously unseen
```

Maximum per run:

```text
max_scores_per_run = 30
```

The cap prevents one source explosion from producing excessive LLM usage.

Unscored jobs remain:

```text
match_state = pending
```

for the next run.

---

# 32. Match State

Allowed values:

```text
pending
scoring
scored
error
```

Before scoring:

```text
pending → scoring
```

On success:

```text
scoring → scored
```

On failure:

```text
scoring → error
```

A future discovery run MAY retry `error`.

---

# 33. Qualification Rule

Default:

```python
qualifies = (
    job.active_state != "inactive"
    and job.prefilter_state != "fail"
    and score >= config.minimum_match_score
)
```

Default threshold:

```text
85
```

Unknown active state MAY still qualify when source freshness is reasonable.

Explicitly inactive postings MUST NOT.

---

# 34. Import Service

Create:

```text
cv_optimizer/discovery/importer.py
```

Suggested API:

```python
class DraftImporter:

    def import_job(
        self,
        job_posting_id: int,
    ) -> int:
        """Return application_id."""
```

Do NOT call `tracker.track()` because it currently continues into CV generation.

---

# 35. Draft Import Transaction

Import sequence:

```text
BEGIN

1. reload canonical job
2. verify score >= threshold
3. verify not inactive
4. verify user_state != dismissed
5. verify application_id IS NULL

6. check existing manual applications
7. if equivalent existing app:
       link canonical posting
       do not create duplicate
       COMMIT
       return existing id

8. create applications row
9. create application directory
10. save canonical JD file
11. persist jd_path
12. insert initial status = draft
13. copy job Match Assessment into application Match Assessment
14. link job_postings.application_id
15. set user_state = imported
16. set imported_at = now

COMMIT
```

If any filesystem/database step fails:

```text
ROLLBACK
```

and remove any newly created incomplete application directory.

---

# 36. JD File Format

Automatically discovered JDs should be stored as Markdown or plain text.

Recommended:

```text
applications/
  company_role_123/
    job_description.md
```

Include a small metadata header:

```markdown
# Senior Frontend Engineer

Company: Example Inc.
Source: greenhouse
URL: https://...
Discovered: 2026-08-25
Posted: 2026-08-24
Location: Remote — Europe

---

<canonical JD>
```

The scorer should hash only the actual JD text, not volatile discovery timestamps.

---

# 37. Match Assessment Copy

A qualifying job has already paid the LLM cost.

Do not immediately score the same JD again after creating the application.

If these identities match:

```text
candidate_hash
jd_hash
scoring_version
prompt_version
model_name
```

copy the latest `job_match_assessments` payload into:

```text
match_assessments
```

using the new `application_id`.

No LLM call is needed.

---

# 38. Fix Existing `source` Persistence

There is an existing mismatch:

`track()` accepts `source` and uses it for duplicate detection, but calls:

```python
db.insert_application(company, role, job_url=job_url)
```

without persisting `source`.

Fix:

```python
def insert_application(
    company: str,
    role: str,
    jd_path: str = None,
    cv_path: str = None,
    job_url: str = None,
    source: str = None,
) -> int:
```

SQL:

```sql
INSERT INTO applications (
    company,
    role,
    jd_path,
    cv_path,
    job_url,
    source
)
VALUES (?, ?, ?, ?, ?, ?)
```

Update existing callers.

Discovery source should be persisted as:

```text
auto:serpapi
auto:greenhouse
auto:lever
auto:ashby
```

This makes automatically discovered applications obvious in the TUI.

---

# 39. Existing Manual Application Deduplication

Before auto-importing a job, check existing applications by:

### Priority 1

Normalized `job_url`.

### Priority 2

Company + role + sufficiently equivalent JD.

### Priority 3

Existing source identity if available.

If a corresponding manually created application already exists:

```text
job_postings.application_id = existing.id
job_postings.user_state = imported
```

Do not create another application.

If appropriate, attach/copy the newly calculated match assessment.

---

# 40. Automatic CV Generation

Default:

```json
{
  "auto_generate_cv": false,
  "auto_generate_cover_letter": false
}
```

This is intentional.

Discovery can easily produce:

```text
5
10
20
```

strong jobs.

Generating all artifacts immediately wastes:

- LLM tokens;
- PDF work;
- filesystem clutter;
- attention.

The TUI already provides explicit CV/CL generation actions.

Future optional behavior:

```json
{
  "auto_generate_cv": true,
  "auto_generate_cv_min_score": 95
}
```

may generate a CV for only exceptional matches.

This MUST remain opt-in.

Cover letters SHOULD remain manual by default even then.

---

# 41. Activity / Staleness Model

Create:

```text
cv_optimizer/discovery/activity.py
```

A posting has:

```text
active_state
active_confidence
last_seen_at
```

---

# 42. ATS Activity Rules

For direct ATS feeds:

```text
posting returned by current public feed
→ active
→ confidence high
```

If a previously known posting disappears:

```text
first absence
→ retain current state

second consecutive absence
→ inactive
```

This avoids transient network/API problems immediately closing jobs.

---

# 43. Aggregator Activity Rules

Aggregator result:

```text
active = unknown or active
confidence = medium
```

depending on available data.

Respect:

```text
posted_at
```

and:

```text
max_post_age_days
```

Default:

```text
30 days
```

If a direct ATS source later confirms the same canonical job:

```text
active_confidence = high
```

---

# 44. Job Updates

When an existing job is seen again:

```text
last_seen_at = now
```

If description changes:

```text
description = new_description
description_hash = new_hash
match_state = pending
```

Do not overwrite historical Match Assessments.

A new assessment should be appended.

---

# 45. Dismissal Semantics

If the user decides:

> I do not want this job.

the system must remember this.

Set:

```text
job_postings.user_state = dismissed
job_postings.dismissed_at = now
```

A dismissed posting MUST NOT be auto-imported again even if:

- rediscovered through another source;
- discovered tomorrow;
- score remains above 85.

If its JD materially changes enough to plausibly represent a new vacancy, future logic may allow reconsideration, but MVP should remain conservative.

---

# 46. Deleting an Auto-Imported Draft

Current TUI deletion removes applications.

For a linked discovered application, deletion must first mark the source posting:

```text
user_state = dismissed
dismissed_at = now
```

Then delete the application.

Because:

```text
job_postings.application_id
```

uses:

```text
ON DELETE SET NULL
```

the discovery record survives and prevents re-import.

Without this behavior:

```text
delete draft
→ next scheduled run
→ same job reappears
```

which would be extremely annoying.

---

# 47. TUI Changes

The current application table contains:

```text
#
Company
Role
Status
Readiness
Source
Created
JD
CV
CL
```

and currently has no Match column.

Add:

```text
Match
```

Recommended order:

```text
#
Company
Role
Match
Status
Readiness
Source
Created
JD
CV
CL
```

Width:

```text
5
```

Example:

```text
  #  Company       Role                         Match  Status   Source
  1  Dash0         Senior Product Engineer        97   draft    auto:serpapi
  2  Example       Senior Vue Engineer            94   draft    auto:ashby
  3  Example AI    Product Engineer               89   draft    auto:greenhouse
```

---

# 48. Match Display

Suggested colors:

```text
85–100  bold green
70–84   yellow
55–69   orange/yellow
<55     red/dim
none    —
```

Auto-discovered applications normally only enter the table at 85+, but manually tracked applications may have any score.

---

# 49. Avoid N+1 Match Queries

Do not render the table by calling:

```text
get_latest_match(app_id)
```

once for every application.

Add a batch DB query:

```python
def get_latest_matches(
    application_ids: list[int] | None = None
) -> dict[int, dict]:
    ...
```

or include latest score in the main application dashboard query.

Do the same eventual cleanup for readiness if convenient.

---

# 50. Detail Panel

For an auto-discovered job, Enter/detail should show:

```text
MATCH                                         94 STRONG

Confidence                                    HIGH
Source                                   auto:ashby
Posted                                  2026-08-24
Discovered                              2026-08-25
Location                           Remote — Europe
Salary                          €80k–€110k / year
URL                               https://...

Strong matches
  + TypeScript
  + complex frontend applications
  + product collaboration
  + design systems
  + accessibility
  + real-time UI

Transferable
  ~ Svelte → substantial React/Vue/Preact background

Gaps
  - no production Svelte evidence

Eligibility
  ✓ remote Europe
```

The framework transfer MUST be visibly labelled as transferable, not direct.

---

# 51. Manual Discovery From TUI

Add binding:

```python
Binding("J", "discover_jobs", "Discover")
```

Current binding set has no discovery action.

`J` SHALL:

1. launch discovery in a Textual worker;
2. keep the UI responsive;
3. update the status bar;
4. refresh the table at completion.

Example:

```text
Discovering jobs…
Fetched 84 · 31 new · 14 eligible · scoring 8/14
```

Completion:

```text
✓ 4 new 85%+ job matches added
```

If none:

```text
No new 85%+ matches.
```

---

# 52. Discovery TUI Progress

Do not expose noisy per-request logs in the main UI.

Status states:

```text
Fetching…
Normalizing…
Filtering…
Scoring 4/12…
Importing…
Complete
```

Detailed errors remain in logs.

---

# 53. CLI

Extend the launcher.

Required:

```bash
./cv-opt discover
```

Optional commands:

```bash
./cv-opt discover --source serpapi

./cv-opt discover --max-scores 10

./cv-opt discover --no-import

./cv-opt discover --rescore

./cv-opt discover --preview
```

Semantics:

### `discover`

Full production flow:

```text
fetch
filter
score
import >=85
```

### `--preview`

```text
fetch
normalize
dedupe
prefilter
```

No LLM calls.

No applications created.

Useful for debugging search configuration.

### `--no-import`

Run scoring/persistence but do not create application Drafts.

Useful for tuning the threshold.

### `--rescore`

Ignore the current job Match Score cache and generate new assessments.

---

# 54. Discovery Service

Suggested orchestration:

```python
class DiscoveryService:

    def run(
        self,
        *,
        sources: list[str] | None = None,
        import_matches: bool = True,
        preview: bool = False,
        force_rescore: bool = False,
        max_scores: int | None = None,
    ) -> DiscoveryRunResult:
        ...
```

Pseudo-flow:

```python
run = db.create_discovery_run()

jobs = []

for query in build_queries(config):
    for source in enabled_sources:
        jobs.extend(
            safe_fetch(source, query)
        )

normalized = normalize(jobs)

canonical_jobs = []

for job in normalized:
    canonical = upsert_and_dedupe(job)
    canonical_jobs.append(canonical)

candidates = []

for job in canonical_jobs:
    result = prefilter(job)

    db.set_prefilter_result(job.id, result)

    if result.state != "fail":
        candidates.append(job)

candidates = prioritize(candidates)

for job in candidates[:max_scores]:
    if has_valid_cached_score(job):
        score = get_cached_score(job)
    else:
        score = MatchService().score_job_posting(job.id)

    if qualifies(job, score):
        if import_matches:
            DraftImporter().import_job(job.id)

finish_run()
notify_if_needed()
```

---

# 55. Search Query Builder

Implement deterministic query generation.

Do not ask an LLM to generate daily search queries.

Example:

```python
roles = [
    "frontend engineer",
    "frontend developer",
    "product engineer",
    "software engineer frontend",
    "full stack engineer typescript",
]
```

Produce profiles such as:

```text
Warsaw:
  frontend engineer
  frontend developer
  product engineer
  ...

Remote:
  frontend engineer remote
  frontend developer remote
  ...
```

Avoid combining every permutation:

```text
role × framework × seniority × geography
```

That would create needless API cost and duplicates.

Seniority can largely be classified after retrieval.

---

# 56. Cost Controls

The discovery pipeline MUST minimize paid LLM operations.

Order of savings:

```text
1. source identity dedupe
2. cross-source dedupe
3. JD length validation
4. location filter
5. role/seniority filter
6. activity filter
7. hash cache
8. only then LLM
```

Default:

```text
max_scores_per_run = 30
```

If there are 100 candidates:

```text
30 score now
70 remain pending
```

Prioritize newest jobs.

---

# 57. Match Cache

Existing Match Score already keys cached results on candidate/JD/scoring identity.

Preserve that concept for jobs.

Cache identity:

```text
job_posting_id
candidate_hash
jd_hash
scoring_version
prompt_version
model_name
```

A score is reusable only if all identity fields match.

Changing:

```text
master_cv.json
```

therefore naturally causes new candidate hashes and re-scoring.

Changing:

```text
match-v1 → match-v2
```

also invalidates the cache cleanly.

---

# 58. Scheduling

Discovery must be runnable without FastAPI.

Do not require:

```text
localhost:8000
```

to be running.

The command should operate directly against:

```text
SQLite
MatchService
source adapters
```

This also removes the old Milestone 3 requirement to maintain a queue just because `/api/track` might be offline.

---

# 59. macOS Scheduling

Add:

```text
scripts/install_discovery_launchd.sh
scripts/uninstall_discovery_launchd.sh
```

The launch agent should execute:

```text
<repo>/.venv/bin/python <repo>/cv_optimizer.py discover
```

Default:

```text
08:00 daily
```

Configuration should make it easy to move to:

```text
every 6 hours
```

later.

Do not hardcode the user's home path into a checked-in plist.

Generate the plist during installation.

---

# 60. Concurrency Lock

Scheduled discovery and manual `J` discovery may overlap.

Use a lock file:

```text
.discovery.lock
```

On macOS/Linux:

```python
fcntl.flock(..., LOCK_EX | LOCK_NB)
```

If already running:

```text
Discovery already in progress.
```

Exit cleanly.

Do not run two scoring/import processes simultaneously.

---

# 61. Notifications

Only notify when something useful happened.

If:

```text
imported_count > 0
```

send:

```text
Spray and Pray
4 new 85%+ job matches added
```

Optionally include top three:

```text
97 Dash0 — Senior Product Engineer
94 Example — Senior Vue Engineer
91 ExampleAI — Product Engineer
```

No notification when:

```text
imported_count == 0
```

Do not send one notification per job.

Batch them.

---

# 62. Discord

If Discord notifications are configured, send one summary:

```text
🎯 4 new job matches

97% — Dash0 — Senior Product Engineer
94% — Example — Senior Vue Engineer
91% — Example AI — Product Engineer
89% — Example — Fullstack Engineer
```

Include application URLs where known.

Failures in Discord MUST NOT fail discovery.

---

# 63. Failure Handling

## Source failure

```text
SerpApi fails
→ log
→ mark source error
→ continue Lever/Ashby/etc.
```

---

## HTTP 429

```text
stop requesting that provider for this run
record rate-limit error
continue other providers
```

Do not busy-retry indefinitely.

---

## Invalid/missing description

If normalized JD length is below the existing scoring minimum:

```text
prefilter_state = fail
prefilter_reason = insufficient_description
```

Current Match Score requires at least 120 normalized JD characters.

---

## LLM failure

```text
match_state = error
```

Do not import.

Allow retry on a future run.

---

## Import failure

Rollback DB transaction and clean incomplete filesystem artifacts.

Do not leave:

```text
application row
without JD
```

or:

```text
directory
without application row
```

---

# 64. Observability

At INFO level, one discovery run should produce concise logs:

```text
Discovery run #42 started
serpapi: fetched 61
lever: fetched 23
ashby: fetched 18

102 raw results
74 unique canonical postings
41 already known
33 new/changed
19 failed prefilter
14 queued for score

14 scored
5 >= 85
4 imported
1 already tracked manually

Discovery run #42 completed
```

Do not log full JD text.

Do not log API secrets.

---

# 65. Source Metrics

Store per-source stats in:

```text
source_stats_json
```

Example:

```json
{
  "serpapi": {
    "requests": 8,
    "fetched": 61,
    "new": 21,
    "errors": 0
  },
  "lever": {
    "requests": 5,
    "fetched": 23,
    "new": 7,
    "errors": 0
  }
}
```

This will later show which sources actually produce useful applications.

---

# 66. Suggested Future Discovery View

Not required for MVP, but the data model deliberately supports a later TUI screen:

```text
DISCOVERED JOBS

Score  Company      Role                     State
 97    Dash0        Senior Product Engineer  imported
 84    Foo          Senior Vue Engineer      pending
 79    Bar          Angular Engineer         pending
 72    Baz          Frontend Developer       dismissed
```

This would let the user inspect jobs below 85 and manually promote one.

Do not block Milestone 3 on building this screen.

---

# 67. Testing — Source Adapters

Fixtures MUST be checked into:

```text
tests/fixtures/jobs/
```

Do not run live provider APIs in the normal unit test suite.

Tests:

```text
SerpApi JSON → DiscoveredJob
Lever JSON → DiscoveredJob
Ashby JSON → DiscoveredJob
Greenhouse JSON → DiscoveredJob
```

Verify:

- title;
- company;
- description;
- URL;
- location;
- posted time;
- work model;
- compensation when provided.

---

# 68. Testing — Prefilter

Required cases:

```text
Senior Frontend Engineer — Warsaw hybrid
→ PASS

Frontend Engineer — Remote Europe
→ PASS

Frontend Developer — Remote worldwide
→ PASS

Angular Developer — Remote Poland
→ PASS

Svelte Engineer — Warsaw
→ PASS

Junior React Developer
→ FAIL

Frontend Intern
→ FAIL

Python Backend Engineer
→ FAIL

Senior Frontend Engineer — New York onsite
→ FAIL

Frontend Engineer — US remote only
→ FAIL

Frontend Engineer — "Remote" with unspecified region
→ REVIEW
```

Most importantly:

```text
different JS framework
```

must never itself return FAIL.

---

# 69. Testing — Framework Transferability

Add deterministic fixtures.

### Test A

Candidate:

```text
React + Vue + Next + TypeScript
```

JD:

```text
Angular frontend
```

without deep specialization.

Expected:

```text
Angular evidence = framework_transfer
evidence value = 0.92
no missing-core hard cap
```

---

### Test B

JD:

```text
6+ years Angular
RxJS
NgRx
Angular Signals
```

Expected:

```text
Angular tenure = framework_depth_gap
RxJS = based on actual evidence
NgRx = none if absent
Signals = none if absent
```

The job may score below 85.

---

### Test C

Candidate explicitly has Vue.

JD:

```text
Vue 3
```

Expected:

```text
direct
```

---

### Test D

JD:

```text
SvelteKit
modern frontend framework experience
```

Expected:

```text
framework_transfer
```

not:

```text
none
```

---

### Test E

JD:

```text
Python backend development
```

React experience MUST NOT create framework transfer.

Expected:

```text
none
```

---

# 70. Testing — Hard Caps

Prove:

```text
Angular mismatch classified framework_transfer
```

does NOT cause:

```text
score <= 69
```

solely because Angular was named as core.

Also prove:

```text
mandatory Kubernetes
candidate has no Kubernetes
```

still produces a true missing-core gap when appropriate.

The existing `none` hard-gap behavior must remain intact.

---

# 71. Testing — Deduplication

Required:

### Same source ID

```text
same Lever posting twice
→ one job_posting
→ one job_source_ref
```

### Cross-source same job

```text
Google Jobs result
+
Ashby direct posting
```

→ one `job_posting`, two `job_source_refs`.

### Same title, different vacancy

```text
Company X — Senior Frontend Engineer — Warsaw
Company X — Senior Frontend Engineer — Berlin
```

→ two canonical postings.

---

# 72. Testing — Caching

### Unchanged JD

Run discovery twice.

Expected second run:

```text
0 new LLM calls
```

for unchanged postings.

### Changed JD

Change description.

Expected:

```text
new hash
new assessment
```

### Match version change

Existing:

```text
match-v1
```

Current:

```text
match-v2
```

Expected:

```text
new assessment
```

---

# 73. Testing — Import Threshold

```text
score = 85
→ Draft created

score = 100
→ Draft created

score = 84
→ no application

score = 85 + inactive
→ no application
```

---

# 74. Testing — Draft State

For auto-imported matching job:

```text
latest_status == draft
cv_path IS NULL
cover_letter_path IS NULL
jd_path IS NOT NULL
job_url IS NOT NULL
source == auto:<provider>
```

No `applied` status exists.

---

# 75. Testing — Match Copy

Given:

```text
job_match_assessment score=94
```

import the job.

Expected:

```text
application match assessment = 94
```

and LLM mock call count remains unchanged during import.

---

# 76. Testing — Deletion/Dismissal

Import job:

```text
job → application #42
```

Delete application from TUI.

Expected:

```text
job.user_state = dismissed
job.application_id = NULL
```

Run discovery again.

Expected:

```text
same job is NOT imported again
```

---

# 77. Testing — Existing Manual Application

Manually tracked job already exists.

Discovery finds equivalent job at 96%.

Expected:

```text
no duplicate application
job_posting.application_id = existing application
```

---

# 78. Implementation Order

## Phase 0 — Compatibility fixes

Implement first:

- persist `source` correctly in `insert_application`;
- add tests around existing application tuple behavior;
- do not alter `applications` schema;
- establish `match-v2` version constants/config.

**Done when:** existing manual and browser-extension workflows still pass.

---

## Phase 1 — Framework Match v2

Implement:

- framework family normalization;
- new evidence levels;
- new values;
- prompt changes;
- positive-evidence validation;
- tests;
- version bump.

**Done when:** Vue/Angular/Svelte generic framework roles no longer receive disproportionate penalties.

---

## Phase 2 — Discovery persistence

Implement:

- `job_postings`;
- `job_source_refs`;
- `job_match_assessments`;
- `discovery_runs`;
- DB access functions.

**Done when:** normalized jobs can be persisted without creating applications.

---

## Phase 3 — Normalization and filtering

Implement:

- source-neutral model;
- role classifier;
- seniority classifier;
- location/work-model classifier;
- prefilter.

**Done when:** fixture jobs can be classified PASS/FAIL/REVIEW without LLM calls.

---

## Phase 4 — SerpApi source

Implement:

- query builder;
- HTTP client;
- pagination;
- rate-limit behavior;
- response normalization.

**Done when:**

```bash
./cv-opt discover --preview
```

returns real, normalized, deduplicated jobs.

---

## Phase 5 — Job scoring

Refactor:

```text
MatchService
```

into text-level analysis plus persistence wrappers.

Implement:

```text
score_job_posting()
```

**Done when:** a discovered posting receives a Match Score without an application row.

---

## Phase 6 — Auto-import

Implement:

```text
DraftImporter
```

and threshold logic.

**Done when:** an active 85+ job becomes a Draft with JD + Match Score but without generated CV/CL.

---

## Phase 7 — TUI

Implement:

- Match column;
- discovery binding `J`;
- progress/status;
- discovery metadata in details;
- deletion/dismissal behavior.

**Done when:** newly discovered Drafts can be understood and triaged without leaving the TUI.

---

## Phase 8 — Direct ATS adapters

Implement:

```text
Lever
Ashby
Greenhouse
```

with source-ref deduplication.

**Done when:** an aggregator result and direct ATS result merge into one canonical vacancy.

---

## Phase 9 — Scheduling and notifications

Implement:

- CLI standalone discovery;
- launchd installer;
- lock;
- macOS notification;
- Discord batch summary.

**Done when:** discovery can run unattended without FastAPI/TUI running.

---

# 79. Acceptance Criteria

The milestone is complete only when all of the following are true.

### Discovery

- [ ] `./cv-opt discover` fetches current jobs from at least one broad source.
- [ ] Search queries are role-centric, not React-centric.
- [ ] Warsaw onsite/hybrid jobs are included.
- [ ] Remote Poland/Europe/EMEA/worldwide jobs are included.
- [ ] Mid and Senior jobs are included.
- [ ] Angular/Vue/Svelte/etc. jobs are not filtered merely because of framework choice.

### Normalization

- [ ] Every provider maps to one canonical `DiscoveredJob` schema.
- [ ] JD text is available for every job passed to Match Score.
- [ ] Jobs with unusably short JDs are rejected before LLM scoring.

### Deduplication

- [ ] Provider ID duplicates do not create multiple jobs.
- [ ] Cross-source copies merge when confidently equivalent.
- [ ] Different vacancies at the same company are not incorrectly merged.

### Matching

- [ ] Discovered jobs can be scored without first creating an application.
- [ ] Existing application scoring still works.
- [ ] `match-v2` implements framework transferability.
- [ ] Generic framework mismatch creates only a small penalty.
- [ ] Deep exact-framework specialization can create a material penalty.
- [ ] Framework mismatch alone does not trigger the `none` hard-gap cap.
- [ ] Independent missing technologies remain true gaps.
- [ ] Match history remains versioned and auditable.

### Import

- [ ] `>=85` active jobs automatically create Drafts.
- [ ] `<85` jobs remain only in discovery persistence.
- [ ] Auto-imported Drafts contain their JD.
- [ ] Auto-imported Drafts contain their Match Score.
- [ ] Auto-imported Drafts do not contain a generated CV by default.
- [ ] Auto-imported Drafts do not contain a generated cover letter by default.
- [ ] Auto-imported Drafts are never marked `applied`.
- [ ] Existing manually tracked jobs are not duplicated.
- [ ] Deleted/dismissed discoveries do not immediately reappear.

### TUI

- [ ] Match Score is visible in the application table.
- [ ] Auto-discovered source is visible.
- [ ] Detail view shows strengths, transferable skills and gaps.
- [ ] Framework transfer is visibly distinguished from direct evidence.
- [ ] `J` runs discovery without blocking the UI.
- [ ] Completion reports how many new qualifying Drafts were created.

### Scheduling

- [ ] Discovery can run with the FastAPI server stopped.
- [ ] A scheduled run can execute unattended.
- [ ] Concurrent discovery runs are prevented.
- [ ] No notification is emitted when zero new jobs qualify.
- [ ] A single summary notification is emitted when jobs qualify.

### Cost / reliability

- [ ] Duplicate jobs are removed before LLM scoring.
- [ ] Explicitly incompatible jobs are filtered before LLM scoring.
- [ ] Unchanged JDs reuse cached results.
- [ ] Match-version changes invalidate the relevant cache.
- [ ] One failed source does not stop other sources.
- [ ] A rate-limited source does not busy-loop.
- [ ] Failed imports leave no half-created applications.

---

# 80. Definition of Done — User-Level Scenario

Given the application is configured with:

```text
threshold = 85

seniority:
  mid
  senior

locations:
  Warsaw onsite/hybrid
  Poland remote
  Europe remote
  worldwide remote

framework policy:
  transferable_js
```

and a scheduled discovery run finds:

```text
Role A
Senior Angular Frontend Engineer
Warsaw hybrid
Match = 91

Role B
Senior Svelte Engineer
Remote Europe
Match = 88

Role C
React Developer
Remote US only
Potential skills match = 96

Role D
Senior Frontend Engineer
Remote Europe
Match = 79
```

the final application table SHALL contain:

```text
Role A — draft — 91
Role B — draft — 88
```

It SHALL NOT contain:

```text
Role C
```

because geography contradicts the search policy.

It SHALL NOT contain:

```text
Role D
```

because Match Score is below 85.

However Role D SHALL remain in `job_postings` with its score so that it can be reconsidered without rediscovering/re-scoring it unnecessarily.

Neither Role A nor Role B SHALL have a generated CV or cover letter until the user explicitly requests generation.

This is the intended Milestone 3 behavior.

---

# 81. Resulting Product Architecture

After implementation, Spray and Pray becomes:

```text
                         ┌────────────────────┐
                         │   master_cv.json   │
                         └─────────┬──────────┘
                                   │
                                   ▼
┌──────────────┐          ┌───────────────────┐
│ Job Sources  │─────────▶│ Discovery Engine  │
└──────────────┘          └─────────┬─────────┘
                                   │
                                   ▼
                          ┌───────────────────┐
                          │ Canonical Jobs DB │
                          └─────────┬─────────┘
                                   │
                             prefilter
                                   │
                                   ▼
                          ┌───────────────────┐
                          │   Match Score v2  │
                          └─────────┬─────────┘
                                   │
                             score >= 85
                                   │
                                   ▼
                          ┌───────────────────┐
                          │ Application Draft │
                          └─────────┬─────────┘
                                   │
                         explicit user action
                                   │
                   ┌───────────────┴──────────────┐
                   ▼                              ▼
             Generate CV                  Generate Cover Letter
                   │                              │
                   └───────────────┬──────────────┘
                                   ▼
                               Apply
                                   │
                                   ▼
                         Existing SAP Pipeline
```

The core principle is:

> **Spray and Pray should autonomously find opportunities, but it should not autonomously pretend an application has been made.**

Discovery is automatic.

Matching is automatic.

Strong-match Draft creation is automatic.

Candidate-document generation remains deliberate by default.

Submission remains deliberate until a later, separately specified automation milestone.