# ProofMode Checkpoints

This document is the practical build plan for ProofMode. It turns the product vision into 16 checkpoints that we can complete, test, commit, and review one by one.

The goal is not to rush through the list. The goal is to keep every step understandable, useful, and demoable.

## Timeline Overview

| Week | Theme | Outcome |
| --- | --- | --- |
| Week 1 | Foundation | ProofMode can accept a claim, create a run, and return a structured report. |
| Week 2 | UI verification | ProofMode can use a browser to catch ghost completion. |
| Week 3 | API and data verification | ProofMode can catch contract drift and state blindness. |
| Week 4 | Planner, dashboard, and polish | ProofMode feels like a real verification product. |

## Week 1: Foundation And Core Shape

### Checkpoint 1: Product Definition

Define the language of the project so every future feature has a clear place.

Key terms:

- Claim: what the AI agent says it completed.
- Task: the original request being verified.
- Verification run: one ProofMode attempt to prove or reject a claim.
- Checklist: the planned checks ProofMode will run.
- Verifier: one module that checks a specific layer.
- Evidence: screenshots, logs, API responses, DB snapshots, diffs, or reports.
- Verdict: `passed`, `failed`, or `uncertain`.

Acceptance criteria:

- The README explains ProofMode in plain language.
- The roadmap explains the major verification layers.
- The codebase has types or schemas for runs, checks, and statuses.

Current status:

- Started.

### Checkpoint 2: Initial Project Structure

Create the starting structure for backend, frontend, generated evidence, and docs.

Target structure:

```txt
backend/
  app/
    main.py
    database.py
    routers/
    schemas/
    services/
    verifiers/
  tests/

frontend/
  src/
    components/
    pages/
    services/
    types/

proofmode-runs/
  reports/
  screenshots/
  logs/

docs/
```

Acceptance criteria:

- Backend and frontend folders exist.
- Generated run artifact folders exist.
- Documentation lives under `docs/`.
- `.gitignore` prevents generated evidence and dependency folders from being committed.

Current status:

- Started.

### Checkpoint 3: Minimal Backend

Build the first FastAPI backend surface.

Required endpoints:

```txt
GET /health
POST /runs
GET /runs
GET /runs/{run_id}
```

`POST /runs` should accept:

```json
{
  "claim": "I added user login",
  "repo_path": "...",
  "target_url": "http://localhost:3000",
  "api_base_url": "http://localhost:8000"
}
```

Acceptance criteria:

- The backend starts locally.
- A run can be created from a claim.
- Created runs can be listed.
- A missing run returns `404`.

Current status:

- Started.

### Checkpoint 4: First Proof Report Format

Define the first structured ProofMode result.

Example:

```json
{
  "run_id": "abc123",
  "claim": "I added user login",
  "verdict": "failed",
  "checks": [
    {
      "layer": "ui",
      "status": "failed",
      "summary": "Login button exists but click produced no navigation",
      "evidence": {}
    }
  ]
}
```

Acceptance criteria:

- Every run has a final status.
- Every check has a layer, status, summary, and evidence object.
- Every run includes a timeline of planner, verifier, report, and completion events.
- Reports can later be converted to Markdown.
- Run records are persisted so verification history survives backend restarts.

Current status:

- Started.

## Week 2: UI Verification Layer

### Checkpoint 5: Playwright Runner

Add the first real verifier: UI verification with Playwright.

ProofMode should:

- Open the target app in a browser.
- Visit the target page.
- Check page load success.
- Check that elements exist, are visible, and are clickable.
- Capture browser console errors.
- Capture failed network requests.

Acceptance criteria:

- `UiVerifier` runs real browser checks when `target_url` is provided.
- A missing or unreachable page returns a failed or uncertain UI check.
- Console and network failures are included in evidence.

Current status:

- Started.

### Checkpoint 6: Before And After Screenshots

Capture visual evidence for UI verification.

Target output:

```txt
proofmode-runs/
  {run_id}/
    before.png
    after.png
    console-errors.json
    network-errors.json
```

Acceptance criteria:

- Each UI run creates a run-specific artifact folder.
- Screenshots are saved with stable file paths.
- Screenshot paths are returned as evidence.

Current status:

- Started.

### Checkpoint 7: Simple UI Assertion Format

Define the first user-readable UI check format.

Example:

```json
{
  "page": "/login",
  "checks": [
    {
      "type": "text_present",
      "value": "Login"
    },
    {
      "type": "element_clickable",
      "selector": "[data-testid='sign-in-button']"
    }
  ]
}
```

Supported first check types:

- `page_loads`
- `text_present`
- `element_exists`
- `element_visible`
- `element_clickable`
- `console_errors_absent`

Acceptance criteria:

- UI checks are represented as structured data.
- The planner can generate basic UI checks.
- The UI verifier can execute those checks.

Current status:

- Started.

### Checkpoint 8: Human-Readable UI Report

Make UI verification understandable to a human reviewer.

The report should show:

- Claim.
- Final verdict.
- UI check results.
- Screenshots.
- Console errors.
- Network errors.
- Suggested reason for failure.

Acceptance criteria:

- Markdown report includes UI evidence.
- Frontend displays UI check results.
- Frontend can link to or preview screenshot evidence.

Current status:

- Started.

## Week 3: API And Data Verification

### Checkpoint 9: API Contract Verification

Add HTTP assertions using `httpx`.

ProofMode should:

- Call affected endpoints.
- Check response status codes.
- Validate required fields.
- Extract response schema.
- Detect missing or renamed fields.

Example:

```json
{
  "method": "GET",
  "path": "/api/users",
  "expected_status": 200,
  "required_fields": ["id", "email", "name"]
}
```

Acceptance criteria:

- API checks run when `api_base_url` is provided.
- Failed requests return useful evidence.
- Status code mismatches are reported.
- Missing fields are reported.

Current status:

- Started.

### Checkpoint 10: API Snapshot System

Store API response shapes so future runs can detect contract drift.

Target output:

```txt
proofmode-runs/
  snapshots/
    api/
      users.get.json
```

Snapshot should include:

- endpoint path
- HTTP method
- status code
- extracted response schema
- schema hash

Acceptance criteria:

- API snapshots can be saved.
- Later snapshots can be compared.
- Contract changes produce structured issues.

Current status:

- Started.

### Checkpoint 11: DB Verification

Add database state checks.

ProofMode should support checks like:

- Did a row get created?
- Did a row update?
- Did a table exist?
- Did a column exist?
- Did a schema change unexpectedly?

Example:

```json
{
  "table": "users",
  "expect": {
    "column_exists": "last_login_at"
  }
}
```

Acceptance criteria:

- DB checks run when a database URL is configured.
- Schema checks work for selected tables.
- Row count checks work for selected tables.
- Failures are reported without exposing too much sensitive data.

Current status:

- Started.

### Checkpoint 12: Data Snapshot Compare

Compare database state before and after a task.

Example:

```txt
Before:
users: 10 rows
columns: id, email, name

After:
users: 10 rows
columns: id, email, name, last_login_at
```

Acceptance criteria:

- Before and after DB snapshots are saved.
- Schema changes are detected.
- Row count changes are detected.
- The report explains whether the expected data change happened.

Current status:

- Started.

## Week 4: Planner, Git Diff, And Product Polish

### Checkpoint 13: Git Diff Analysis

Analyze changed files to decide what needs proof.

Example changed files:

```txt
frontend/src/pages/Login.tsx
backend/app/routes/auth.py
backend/app/models/user.py
```

Expected inference:

- Frontend changed: run UI checks.
- API route changed: run API checks.
- Model or migration changed: run DB checks.
- Shared logic changed: run broader checks.

Acceptance criteria:

- ProofMode can list changed files from Git.
- Files are categorized by area.
- The planner uses diff categories to recommend verification layers.

Current status:

- Started.

### Checkpoint 14: Verification Planner

Build the planner that decides which checks to run.

First version:

- Deterministic planner using claim text, URLs, and changed files.

Later version:

- LLM-assisted planner that generates richer checklists.

Example output:

```json
{
  "changed_files": ["routes/auth.py", "Login.tsx"],
  "recommended_checks": ["ui", "api"],
  "reason": "Frontend and auth API files changed"
}
```

Acceptance criteria:

- Every run has a checklist.
- Checklist is visible in the API response.
- Checklist is visible in the frontend.
- The planner can be improved without rewriting verifiers.

Current status:

- Started.

### Checkpoint 15: Report UI

Make the frontend useful as a review surface.

Required views:

- Run list.
- Run detail.
- Agent behavior timeline.
- Layer-by-layer results.
- Screenshot evidence.
- API response diffs.
- DB state diffs.
- Git changed files.
- Final verdict.

Acceptance criteria:

- A reviewer can understand what passed and failed.
- Evidence is visible without reading raw JSON.
- The timeline shows what ProofMode did in order for each run.
- Failed checks stand out clearly.

Current status:

- Partially started with the dashboard and run cards.

### Checkpoint 15A: Approval Gate

Turn the dashboard from a passive report viewer into a human decision point.

Required decisions:

- Approve proof.
- Reject proof.
- Request a fix with reviewer instructions.

Acceptance criteria:

- A reviewer can record an approval decision from the run detail page.
- The decision is persisted in the run JSON record.
- The decision appears in the Markdown report.
- The timeline records the human decision event.

Current status:

- Started.

### Checkpoint 15B: Demo Mode

Seed walkthrough runs that make the product value obvious without needing a separate broken app.

Required scenarios:

- Ghost completion: the UI exists but the interaction is not wired.
- Contract drift: an API response shape changed from the baseline.
- State blindness: the API returned success but database state did not change.

Acceptance criteria:

- The backend exposes a demo seed endpoint.
- The dashboard can seed demo runs with one click.
- Demo runs are persisted as JSON records and Markdown reports.
- Demo evidence includes meaningful checklist, timeline, and layer-level failures.

Current status:

- Started.

### Checkpoint 16: Docker Compose

Make local setup predictable.

Services:

```txt
backend
frontend
postgres
```

Acceptance criteria:

- `docker compose up --build` starts the stack.
- Backend is available on `localhost:8000`.
- Frontend is available on `localhost:5173`.
- PostgreSQL is available for DB verification work.

Current status:

- Started, not fully validated.

## Progress Tracking

| Checkpoint | Name | Status |
| --- | --- | --- |
| 1 | Product definition | Started |
| 2 | Initial project structure | Started |
| 3 | Minimal backend | Started |
| 4 | First proof report format | Started |
| 5 | Playwright runner | Started |
| 6 | Before and after screenshots | Started |
| 7 | Simple UI assertion format | Started |
| 8 | Human-readable UI report | Started |
| 9 | API contract verification | Started |
| 10 | API snapshot system | Started |
| 11 | DB verification | Started |
| 12 | Data snapshot compare | Started |
| 13 | Git diff analysis | Started |
| 14 | Verification planner | Started |
| 15 | Report UI | Partially started |
| 16 | Docker Compose | Started |
