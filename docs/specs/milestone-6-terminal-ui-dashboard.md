# Milestone 6: Terminal UI Dashboard (SAP) Specification

**Status:** Draft
**Dependencies:** Milestone 0 (CLI, DB), Milestone 1 (Discord notifications, FastAPI server)
**Framework:** [Textual](https://textual.textualize.io) v6.6+
**Application Name:** Spray And Pray (abbreviated **SAP** or **sap**)

---

## Problem Statement

The current CLI interface (`cv-opt track`, `cv-opt status`, `cv-opt list`) is stateless and read-once — each command fires, prints a table or status line, and exits. There is no way to browse applications interactively, filter by company or status, preview CV paths, edit statuses inline, or see live notifications streaming in. The user must switch mental context to a browser for any action beyond the most basic commands.

We need an interactive terminal dashboard that replaces the flat CLI with a persistent, keyboard-driven UI with no browser required.

---

## Goals

- [ ] Provide a persistent interactive dashboard showing all applications in a paginated, searchable table
- [ ] Enable inline status editing with keybinding actions (apply, mark interview, reject, log notes)
- [ ] Surface live notifications from the existing Discord/Telegram listener in a scrolling ticker
- [ ] Integrate with the existing SQLite DB and LLM/SAP pipeline with no changes to the backend

---

## Out of Scope

- Editing CV content from the TUI (use `sap optimize` or the extension flow)
- A web-based dashboard — the whole point is terminal-only
- Job discovery or submission automation (Milestones 3-5)

---

## Architecture

The TUI is a **read-write view** over the SQLite DB. It queries the DB on mount and on manual refresh, calls the `cv_optimizer.tracker` Python API directly for status changes, and listens for incoming notifications via an in-process bus. The underlying Python package is still `cv_optimizer` (not yet renamed); only the user-facing command and app name are SAP.

```
                    textual App
  ┌──────────────────────────────────────────────────┐
  │              Header (title bar)                   │
  ├──────────────────────────────────────────────────┤
  │              Input (search/filter bar)             │
  ├──────────────────────────────────────────────────┤
  │  DataTable (paginated application list)            │
  │  ┌──────┬──────────┬──────────────┬───────────┐  │
  │  │  #   │ Company  │     Role     │  Status   │  │
  │  ├──────┼──────────┼──────────────┼───────────┤  │
  │  │  42  │ Acme     │ Sr. Engineer │ interview │  │
  │  │  43  │ Beta     │ FE Dev       │ ghosted   │  │
  │  └──────┴──────────┴──────────────┴───────────┘  │
  ├──────────────────────────────────────────────────┤
  │           Detail panel (selected row)              │
  ├──────────────────────────────────────────────────┤
  │     Notification ticker / status bar               │
  ├──────────────────────────────────────────────────┤
  │              Footer (keybinding hints)             │
  └──────────────────────────────────────────────────┘

Data flow:
  ┌──────────┐    SQL query     ┌───────────┐
  │ SQLite DB │  <------------> │ SAP TUI   │
  │ (apps,    │                 │ (in-mem   │
  │  history) │                 │  cache)   │
  └──────────┘                  └─────┬─────┘
                                      │ user actions
                                      v
                              ┌────────────────┐
                              │  cv_optimizer  │
                              │  (Python API)  │
                              └────────────────┘
```

---

## Implementation Steps

### Step 6.1 — Scaffold the TUI Framework

**Objective:** Create a minimal Textual app shell with the layout structure: header, filter bar, body table, detail panel, notification ticker, footer.

**Layout:**

| Region | Widget | Dock | Height |
|---|---|---|---|
| Header | `textual.widgets.Header` | top | 1 |
| Filter bar | `textual.widgets.Input` | top | 3 |
| Body table | `textual.widgets.DataTable` | n/a | 1fr |
| Detail panel | `textual.widgets.Static` | n/a | 5 (collapsible) |
| Notification ticker | `textual.widgets.RichLog` | bottom | 3 |
| Footer | `textual.widgets.Footer` | bottom | 1 |

**File:** `cv_optimizer/tui/app.py`
**Class:** `SapDashboard(App)` with `CSS = "cv_optimizer/tui/dashboard.tcss"`.

**App-level keybindings:**

| Key | Action | Description |
|---|---|---|
| `q` | `quit` | Quit the dashboard |
| `r` | `refresh` | Re-query DB and refresh table |
| `/` | `focus_filter` | Focus the search/filter input |
| `j` / `k` | cursor_down / cursor_up | Navigate table rows (DataTable default) |
| `enter` | `toggle_detail` | Show/hide detail panel for selected row |
| `s` | `change_status` | Change status of selected application |
| `l` | `log_notes` | Open modal to log interview notes |
| `o` | `open_folder` | Open application folder in Finder |
| `ctrl+r` | `regenerate_cv` | Re-generate CV for selected app |
| `n` | `next_page` | Next page of results |
| `p` | `prev_page` | Previous page of results |
| `escape` | `dismiss` | Close detail panel or dismiss modal |

**Acceptance Criteria:**
- [ ] App starts and renders the layout with placeholder text in each panel
- [ ] Header shows app title "Spray & Pray — Application Dashboard"
- [ ] DataTable has default focus on startup
- [ ] `q` exits cleanly with no unclosed resources

---

### Step 6.2 — Paginated Application Table with Search/Filter

**Objective:** Populate the DataTable from the SQLite DB with pagination, inline search, and status-aware rendering.

**Data Source:** Wrap `cv_optimizer.db.list_applications()` to return all rows. For each application query the most recent status from `status_history`.

**New helper function in `cv_optimizer/db.py`:**
```python
def list_applications_with_status() -> list[dict]:
    """Return all apps with their latest status and full history."""
```

Returns a dict per app: `{id, company, role, jd_path, cv_path, created_at, latest_status, history}`.

**Table Columns:**

| Column | Width | Source |
|---|---|---|
| `#` | 5 | `application.id` |
| `Company` | 25 | `application.company` |
| `Role` | 30 | `application.role` |
| `Status` | 14 | Latest `status_history.status` |
| `Created` | 10 | `application.created_at` (date only) |
| `JD` | 3 | Checkmark if `jd_path` exists |
| `CV` | 3 | Checkmark if `cv_path` exists |

**Status colors in table:**

| Status | Color |
|---|---|
| `applied` | `cyan` |
| `interview N` | `green` |
| `offer` | `bright_green` |
| `accepted` | `bright_green` + bold |
| `rejected` | `red` |
| `ghosted` | `grey` (dim) |

**State:**
```python
class SapDashboard(App):
    def __init__(self):
        self.applications: list[dict] = []
        self.filtered: list[dict] = []
        self.page_size = 20
        self.current_page = 0
        self.filter_text = ""
```

**Filter behavior:**
- When `filter_text` is empty, `filtered = applications` (all)
- When user types in the filter Input, match against `company` OR `role` (case-insensitive substring match)
- Re-paginate on every keystroke

**Pagination metadata:**
- Show "Page N/M — Showing X-Y of Z applications" in a status bar
- `n` / `p` keybindings advance the page, clamped to valid range
- Page size defaults to 20

**Reactive data flow:**
```
on_mount() -> refresh_apps()
  `- worker reads DB -> set applications, filtered, page 0 -> render_table()

on_input_changed() -> apply_filter()
  `- recompute filtered list, reset to page 0, render_table()

action_refresh() -> refresh_apps()
  `- same as on_mount
```

**Acceptance Criteria:**
- [ ] On startup table populates with all applications from the DB
- [ ] Each row shows the correct latest status from `status_history`
- [ ] Typing in the filter Input narrows results in real time matching company or role
- [ ] `n` / `p` keys page through results when they exceed page_size
- [ ] Status column renders in the correct color per table above

---

### Step 6.3 — Context-Sensitive Action Handler

**Objective:** Bind single-key actions to the selected row that interact with the existing SAP pipeline via direct Python API calls.

#### `s` — Change Status

Opens a `ModalScreen` with an Input field for the new status string. Pre-populates the input with the current status.

**Validation:** Reuses `tracker._validate_status()` — accepts `applied`, `rejected`, `ghosted`, `offer`, `accepted`, `interview N`.

On confirm:
1. Call `tracker.update_status(app_id, new_status)` directly (no subprocess)
2. Show a brief notification: "Status updated to interview 1"
3. Re-render the affected row in the table

On invalid status:
1. Show error notification with valid options list
2. Keep modal open for correction

#### `l` — Log Interview Notes

Opens a modal with a multiline `TextArea` widget for interview notes.

On confirm:
1. Save notes to `applications/<app_dir>/notes.md` (append with timestamp and separator)
2. Notify: "Notes saved for <company> — <role>"

#### `o` — Open Application Folder

Calls `open -R <cv_path>` (same pattern as `server.py:/api/open/{id}`) to reveal the CV in Finder. Falls back to `open <app_dir>` if CV path is missing.

On error: "CV path not found at {path}" notification.

#### `ctrl+r` — Regenerate CV

Pushes a confirmation `ModalScreen`: "Re-generate CV for <company> — <role>?"

On confirm:
1. Launch a `@work(exclusive=True, thread=False)` background worker that calls `tracker.track()` with the same JD and company/role
2. Show a progress indicator in the status bar: "Regenerating CV for <company>..."
3. On completion refresh the table and show notification
4. On error show error notification with the LLM error message

#### `enter` — Toggle Detail Panel

When pressed on a selected row the detail panel (collapsible, height=5) populates with:
```
Application #42 — Acme Corp — Senior Engineer
Status: interview 1 (last updated: 2026-06-15 14:30)
JD: applications/acme_senior_engineer/jd.txt
CV: applications/acme_senior_engineer/cv.pdf
Status History: applied -> interview 1
```

Pressing `enter` again or `escape` hides the panel.

**File structure for modals:** `cv_optimizer/tui/screens/modals.py`

Three modal screens:
- `StatusModal(app_id: int, current_status: str)` — Input for new status
- `NotesModal(app_id: int, app_dir: Path)` — TextArea for notes
- `ConfirmModal(title: str, message: str)` — Yes/No confirmation

**Acceptance Criteria:**
- [ ] `s` opens a modal with an Input pre-filled with current status
- [ ] Entering a valid status updates the DB and re-renders the table row
- [ ] Entering an invalid status shows an error notification and keeps modal open
- [ ] `l` opens a text area modal; saving creates/updates `notes.md` in the app directory
- [ ] `o` opens Finder at the CV location or shows notification if no CV
- [ ] `ctrl+r` shows confirmation modal, launches background worker, and refreshes on completion
- [ ] `enter` toggles the detail panel for the selected row
- [ ] `escape` closes modals and detail panel

---

### Step 6.4 — Notification Ticker from Discord Listener

**Objective:** Wire the existing notification pipeline into a scrolling footer ticker so the user sees live updates without leaving the terminal.

**Approach:** In-process notification bus.

Create `cv_optimizer/tui/notifications.py`:
```python
from typing import Callable
from datetime import datetime

class NotificationBus:
    _subscribers: list[Callable[[str], None]] = []

    @classmethod
    def publish(cls, message: str) -> None:
        for cb in cls._subscribers:
            cb(message)

    @classmethod
    def subscribe(cls, callback: Callable[[str], None]) -> None:
        cls._subscribers.append(callback)
```

Refactor `server.py:send_discord_notification` to also call `NotificationBus.publish()` with the same message text. This is a non-breaking change — the Discord webhook still fires. Importing from `cv_optimizer.tui.notifications` from `server.py` is safe because the module has no UI dependencies.

In the TUI app subscribe on mount:
```python
def on_mount(self):
    NotificationBus.subscribe(self._on_notification)

def _on_notification(self, message: str):
    ticker = self.query_one("#ticker", RichLog)
    now = datetime.now().strftime("%H:%M:%S")
    ticker.write(f"[{now}] {message}")
```

The ticker keeps the last ~20 messages. Old messages scroll off as new ones arrive.

**Ticker content prefixes:**

| Source | Prefix | Example |
|---|---|---|
| CV generation | `[CV]` | `[CV] CV generated for Senior Engineer at Acme` |
| Status change | `[STATUS]` | `[STATUS] App #42 -> interview 1` |
| Application submitted | `[APPLY]` | `[APPLY] Auto-applied to Senior Engineer at Acme` |
| Error | `[ERROR]` | `[ERROR] CV generation failed for App #42` |

**Acceptance Criteria:**
- [ ] Ticker appears at the bottom of the dashboard showing the 20 most recent messages
- [ ] When `send_discord_notification` is called the message appears in the ticker within 1 second
- [ ] Each message has a timestamp and type prefix
- [ ] Old messages scroll off as new ones arrive

---

## File Map

| File | Purpose |
|---|---|
| `cv_optimizer/tui/__init__.py` | Package init |
| `cv_optimizer/tui/app.py` | `CvDashboard` App class, compose(), keybindings, main() |
| `cv_optimizer/tui/dashboard.tcss` | Textual CSS for layout and styling |
| `cv_optimizer/tui/notifications.py` | `NotificationBus` singleton |
| `cv_optimizer/tui/screens/__init__.py` | Package init |
| `cv_optimizer/tui/screens/modals.py` | `StatusModal`, `NotesModal`, `ConfirmModal` |
| `cv_optimizer/tui/screens/detail.py` | `DetailPanel` widget for the selected row |

---

## UI States and Transitions

```
  LOADING  (initial mount — worker reading DB)
     |
     v
  BROWSING  <-->  FILTER_ACTIVE  (filter text entered/cleared)
     |
     | keybinding action
     v
   MODAL  (one of StatusInput, NotesEditor, Confirm)
     |
     | confirm / cancel / escape
     v
  BROWSING  (table refreshed)
     |
     | (ctrl+r)
     v
 PROCESSING  (worker running — progress shown in ticker)
     |
     | worker done / error
     v
  BROWSING  (table refreshed, notification posted)
```

---

## Data Flow Summary

| User action | TUI component | Backend call | DB / side effect |
|---|---|---|---|
| Typing in Input | `Input.Changed` -> `apply_filter()` | N/A (in-mem filter) | N/A |
| Pressing "s" + confirm | `StatusModal` -> confirm | `tracker.update_status()` | `status_history` INSERT |
| Pressing "l" + confirm | `NotesModal` -> confirm | file write | `notes.md` on disk |
| Pressing "ctrl+r" + confirm | `ConfirmModal` -> Worker | `tracker.track()` | CV regeneration flow |
| Pressing "r" | `action_refresh()` | `db.list_applications_with_status()` | read-only |
| New notification | Ticker `RichLog` | `NotificationBus.publish()` | Discord webhook |

---

## Error Handling

| Condition | Behavior |
|---|---|
| DB unreachable / corrupted | Show error notification. Table shows empty. Offer `r` to retry. |
| Invalid status entered | Modal stays open. Show error notification with valid options list. |
| CV regeneration fails (LLM timeout, API error) | Show error notification with the error message. Row unchanged. |
| NotificationBus unavailable | Ticker silently unavailable — no TUI crash. |
| App directory deleted externally | `open_folder` shows error notification. Offer to regenerate. |
| Notes file write fails | Show error notification with filesystem error. |

---

## Edge Cases

1. **Empty database** — Table shows a placeholder row: "No applications yet. Use the extension or `sap track` to add one."
2. **Rapid key presses** — Workers use `exclusive=True` so only one regeneration runs at a time.
3. **Window resize** — DataTable should reflow. Textual handles this natively with `1fr` heights.
4. **Very long company/role names** — DataTable columns should truncate with ellipsis (`max-width` in TCSS).
5. **Multiple instances** — Only one TUI instance should run. Check for a PID file or lock on `applications.db` to warn the user.

---

## Testing Strategy

| Scope | Approach |
|---|---|
| Filter logic (`filter.py`) | Unit test — provide list of apps and a filter string, verify filtered output |
| Database helper (`db.list_applications_with_status`) | Unit test against an in-memory SQLite DB |
| Modals | Snapshot test using `textual.testing` or manual verification |
| NotificationBus | Unit test — subscribe, publish, assert callback invoked |
| Integration | Start the TUI with `textual run`, feed test data into DB, verify table rendering by inspecting widgets |

**New CLI entry point:**
```
sap dashboard
```
This launches the Textual app. The CLI entry point (`cv_opt` bash wrapper or renamed `sap` wrapper) should add a new subparser in `cv_optimizer.py:main()`:
```python
dashboard_parser = subparsers.add_parser("dashboard", help="Launch interactive dashboard")
dashboard_parser.set_defaults(func=cmd_dashboard)
```
Where `cmd_dashboard` imports and calls `SapDashboard().run()`.

**Note:** The existing `cv-opt` bash wrapper should be aliased or a new `sap` wrapper created so both `sap track` and `sap dashboard` work. The wrapper at minimum:
```bash
#!/usr/bin/env bash
exec python3 "$(dirname "$0")/cv_optimizer.py" "$@"
```

---

## Dependencies to Add

- `textual>=6.6.0` — the TUI framework
- The `rich` transitive dependency is already pulled in by `textual` and has no conflicts

Update the project to add a `requirements.txt` or `pyproject.toml` to track dependencies.
