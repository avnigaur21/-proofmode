# ProofMode

ProofMode is an agent-agnostic verification layer for AI coding agents. It takes an AI agent's "task complete" claim, runs independent proof checks across UI, API, database state, Git diff evidence, and agent self-report consistency, then produces an auditable verdict before the work is accepted.

ProofMode is not just a test runner. It is a post-execution proof layer that asks:

```txt
What did the agent claim?
What evidence did ProofMode collect?
Does the evidence support, contradict, or only partially support the claim?
Should a human approve this run?
```

## Current Status

ProofMode currently includes:

- FastAPI backend for proof runs, claims, project profiles, artifacts, settings, and approvals
- React + Vite dashboard for run review, saved project profiles, evidence timelines, screenshots, reports, approval gates, and run comparison
- Project-specific reusable API endpoint checks and UI browser flow checks
- Agent-agnostic claim ingestion through `POST /claims/ingest`
- CLI/CI mode through `python -m app.cli verify`
- GitHub PR verification workflow through `.github/workflows/proofmode-pr.yml`
- Evidence bundle export as a ZIP audit package
- Playwright UI verifier with screenshots, console errors, page errors, and network failures
- HTTP API verifier with schema snapshots and contract drift detection
- SQLAlchemy DB verifier with schema and row-count snapshots
- Git diff verifier with changed-file classification and PR diff range support
- Verification planner with deterministic mode, optional LLM mode, and deterministic fallback
- Guarded evidence evaluator with supported, contradicted, and insufficient verdicts
- Agent self-report comparison against executed evidence
- Markdown report generation and persisted JSON run records

## Core Workflow

```txt
Agent, CLI, CI, PR, or dashboard submits a claim
        |
        v
ProofMode normalizes the claim and source metadata
        |
        v
Planner creates a targeted checklist
        |
        v
UI / API / DB / Git diff checks run
        |
        v
Evidence evaluator assigns a guarded verdict
        |
        v
Agent self-report is compared against evidence
        |
        v
Markdown report, JSON records, timeline, and evidence bundle are saved
        |
        v
Human reviewer approves, rejects, or requests fixes
```

## Project Structure

```txt
backend/
  app/
    cli.py
    main.py
    routers/
      artifacts.py
      claims.py
      demo.py
      projects.py
      runs.py
      settings.py
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

.github/
  workflows/
    proofmode-pr.yml

proofmode-runs/
  bundles/
  claims/
  projects/
  reports/
  runs/
  screenshots/
  snapshots/
```

Generated run data under `proofmode-runs/` is ignored by git except for `.gitkeep` placeholders.

## Local Development

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
playwright install chromium
uvicorn app.main:app --reload
```

On Windows PowerShell:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
playwright install chromium
uvicorn app.main:app --reload
```

Use Python 3.12 for the backend environment.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend tests:

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests
```

Frontend build:

```bash
cd frontend
npm run build
```

Docker:

```bash
docker compose up --build
```

## Dashboard

The dashboard supports:

- creating proof runs from a task completion claim
- optional agent self-report input
- saved project profiles
- reusable project API checks and UI flow checks
- configurable proof checks and run presets
- run list search and show-more behavior
- run detail view with claim intake metadata
- evidence evaluation panel
- agent report vs evidence panel
- run-to-run comparison
- approval gate
- planner explainability
- UI/API/DB/Git evidence sections
- behavior timeline
- rendered Markdown report

## Claim Ingestion

ProofMode can accept claims from any source:

```http
POST /claims/ingest
```

Example:

```json
{
  "claim": "Agent says login is complete",
  "agent_report": "I ran tests and verified the login UI.",
  "source": "codex",
  "agent_name": "Codex",
  "project_id": "saved-project-id",
  "external_id": "commit-abc123",
  "metadata": {
    "commit_sha": "abc123",
    "branch": "main"
  }
}
```

ProofMode stores the original claim record under `proofmode-runs/claims/` and links it to a normal proof run.

## CLI / CI Mode

Run ProofMode from the terminal:

```bash
cd backend
python -m app.cli verify --claim "Agent says login is complete" --project "ProofMode local"
```

After installing the backend package in editable mode, the same command is available as:

```bash
proofmode verify --claim "Agent says login is complete" --project "ProofMode local"
```

Run without a saved project:

```bash
python -m app.cli verify \
  --claim "Agent says checkout flow is complete" \
  --agent-report "I ran tests and verified the checkout API" \
  --checks diff \
  --repo-path C:\path\to\repo \
  --source ci \
  --agent-name Codex
```

Exit codes:

- `0`: ProofMode passed
- `1`: ProofMode returned failed or uncertain evidence
- `2`: CLI/setup error

Machine-readable output:

```bash
python -m app.cli verify --claim "Agent says login works" --project "ProofMode local" --json
```

## GitHub PR Integration

ProofMode includes a starter GitHub Actions workflow:

```txt
.github/workflows/proofmode-pr.yml
```

On pull requests, it:

- checks out the PR branch with full Git history
- runs ProofMode through the CLI
- compares the PR range with `--diff-base origin/<base-branch> --diff-head HEAD`
- writes a Markdown PR summary
- uploads JSON records, snapshots, reports, and evidence bundle artifacts
- comments the ProofMode summary on the PR
- fails the GitHub check when ProofMode returns failed or uncertain evidence

The workflow currently runs Git diff verification by default. Full UI/API/DB verification can be enabled by starting the target services in the workflow and passing:

```bash
--target-url ...
--api-base-url ...
--target-db-url ...
--checks full
```

## Evidence Bundle Export

Export a portable ZIP audit package:

```bash
python -m app.cli verify \
  --claim "Agent says login works" \
  --project "ProofMode local" \
  --bundle \
  --bundle-path proofmode-evidence-bundle.zip
```

Download an existing run's bundle:

```bash
curl -L http://localhost:8000/artifacts/bundles/<run-id> -o proofmode-evidence-bundle.zip
```

The bundle includes:

- `manifest.json`
- `summary.md`
- JSON run record
- Markdown report
- claim record
- screenshots when available
- API/DB snapshot evidence
- Git diff evidence
- evaluator verdict
- self-report comparison
- approval decision when recorded

## Agent Self-Report Comparison

ProofMode can compare what the agent says it did against what ProofMode actually verified.

Example:

```txt
Agent report:
"I ran tests, verified the UI click, checked the API, and completed the DB migration."

ProofMode evidence:
Git diff passed.
UI was not checked.
API was not checked.
DB was not checked.
Test evidence is not captured yet.

Self-report verdict:
partially_unsupported
```

Supported comparison verdicts:

- `aligned`
- `partially_unsupported`
- `contradicted`
- `not_provided`

## Verification Layers

UI verification:

- launches Chromium through Playwright
- captures screenshots
- captures console errors
- captures page errors
- captures failed network requests
- supports targeted assertions like text, selector, visibility, and URL checks
- supports saved browser flow steps: click, fill, expect text, expect selector, and expect URL

API verification:

- calls configured HTTP endpoints
- records status codes and JSON shape
- snapshots response schemas
- detects dropped, renamed, or type-changed fields
- supports targeted assertions for method, path, expected status, and required fields
- supports saved multi-endpoint project checks

DB verification:

- connects through SQLAlchemy
- snapshots tables, columns, column types, and row counts
- compares later runs against previous snapshots
- supports targeted assertions for table, column, and row-count delta

Git diff verification:

- classifies changed files as UI, API, DB, logic, or unknown
- recommends proof layers based on changed files
- supports local uncommitted changes
- supports PR/CI diff ranges through `--diff-base` and `--diff-head`

## Planner And Evaluator

Planner modes:

- deterministic planner by default
- optional LLM planner with deterministic fallback

LLM planner configuration:

```bash
PROOFMODE_PLANNER_MODE=llm
PROOFMODE_LLM_PROVIDER=openai
PROOFMODE_LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=...
```

Evaluator behavior:

- returns `supported`, `contradicted`, or `insufficient`
- cannot override deterministic verifier failures
- treats uncertain checks as insufficient evidence
- records confidence, reasons, guardrails, and rubric scores
- optional LLM evaluator can run only after deterministic checks are clean

Runtime status:

```bash
curl http://localhost:8000/settings/status
```

## Demo Runs

Seed walkthrough runs:

```bash
curl -X POST http://localhost:8000/demo/seed
```

The dashboard also exposes a **Seed Demo Runs** button. Demo runs cover:

- ghost completion
- contract drift
- state blindness

## API Reference

Main endpoints:

- `GET /health`
- `POST /runs`
- `GET /runs`
- `GET /runs/{run_id}`
- `POST /runs/{run_id}/approval`
- `POST /claims/ingest`
- `GET /claims`
- `POST /projects`
- `GET /projects`
- `PATCH /projects/{project_id}`
- `DELETE /projects/{project_id}`
- `GET /settings/status`
- `POST /demo/seed`
- `GET /artifacts/reports/{filename}`
- `GET /artifacts/screenshots/{filename}`
- `GET /artifacts/snapshots/{snapshot_type}/{filename}`
- `GET /artifacts/bundles/{run_id}`

## Roadmap

Near-term improvements:

- test ProofMode against 2-3 real projects and record findings
- capture actual test command evidence
- add richer PR configuration for full UI/API/DB workflows
- add dashboard download button for evidence bundles
- add PDF export for evidence bundles
- add stronger semantic self-report parsing
- add project-level verification policies
- add signed or hashed audit manifests

See `docs/REAL_PROJECT_TEST_PLAN.md`, `docs/ROADMAP.md`, and `docs/CHECKPOINTS.md` for validation plans and checkpoint details.
