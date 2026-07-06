# ProofMode

ProofMode is an AI agent verification layer. It intercepts a "task complete" claim and demands proof across UI behavior, API contracts, data state, and code diffs before the claim is treated as true.

This repository starts with the smallest useful version of that idea:

- a FastAPI backend that accepts verification runs
- a React + Vite dashboard that displays run status
- verifier modules for UI, API, DB, and Git diff checks
- an approval gate for accepting, rejecting, or requesting fixes after review
- demo scenarios for ghost completion, contract drift, and state blindness
- a planner that can use Git diff context to generate targeted verification checklists
- a report shape that can grow into screenshots, logs, response diffs, and database evidence

The DB verifier is database-URL based. SQLite works as the first local implementation target, and PostgreSQL support can use the same `target_db_url` contract.

The Git diff verifier is repository-path based. Provide `repo_path` to let ProofMode classify changed files and recommend which proof layers should run.

Run records are persisted as JSON under `proofmode-runs/runs/`, while screenshots, reports, and snapshots are stored in sibling artifact folders. Each run record includes an agent behavior timeline so local verification history remains available after backend restarts and can be inspected later.

## First Checkpoint

The first checkpoint is intentionally simple. We are not trying to solve every verification problem yet. We are creating the stable bones of the product:

1. Submit a claim.
2. Create a ProofMode run.
3. Run placeholder verifiers.
4. Store a structured run record with timeline events.
5. Display runs in the frontend dashboard.
6. Record the human approval decision.

## Project Structure

```txt
backend/
  app/
    main.py
    database.py
    routers/
    schemas/
    models/
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
  runs/
  reports/
  screenshots/
  logs/

docker-compose.yml
```

## Local Development

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload
```

Use Python 3.12 for the backend environment. Some pinned native dependencies do not yet have reliable wheels for Python 3.14.

Backend tests:

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests
```

CLI verification:

```bash
cd backend
python -m app.cli verify --claim "Agent says login is complete" --project "ProofMode local"
```

You can also run without a saved project by passing the target evidence inputs directly:

```bash
python -m app.cli verify \
  --claim "Agent says checkout flow is complete" \
  --checks diff \
  --repo-path C:\path\to\repo \
  --source ci \
  --agent-name Codex
```

The CLI uses the same claim ingestion path as external tools. It stores the claim under `proofmode-runs/claims/`, creates a normal ProofMode run, writes the Markdown report, and exits with:

- `0` when the run passes
- `1` when ProofMode returns failed or uncertain evidence
- `2` for CLI/setup errors such as an unknown project or invalid metadata

For machine-readable CI output:

```bash
python -m app.cli verify --claim "Agent says login works" --project "ProofMode local" --json
```

Evidence bundle export:

```bash
python -m app.cli verify \
  --claim "Agent says login works" \
  --project "ProofMode local" \
  --bundle \
  --bundle-path proofmode-evidence-bundle.zip
```

The evidence bundle is a ZIP audit package. It includes a manifest, summary, JSON run record, Markdown report, claim record, screenshots when available, API/DB snapshot evidence, Git diff evidence, evaluator verdict, and approval decision. Existing runs can also be downloaded from the backend:

```bash
curl -L http://localhost:8000/artifacts/bundles/<run-id> -o proofmode-evidence-bundle.zip
```

PR verification:

ProofMode includes a starter GitHub Actions workflow at `.github/workflows/proofmode-pr.yml`.
On every pull request, it:

- checks out the PR branch with full Git history
- runs `python -m app.cli verify` with `--source github_pr`
- compares the PR range using `--diff-base origin/<base-branch> --diff-head HEAD`
- writes a Markdown PR summary
- uploads the JSON run record, claim record, snapshots, and report as artifacts
- comments the ProofMode summary on the pull request
- fails the GitHub check when ProofMode returns failed or uncertain evidence

The first workflow version runs Git diff verification by default because it does not know how to boot every target app yet. UI, API, and DB verification can be added by starting services in the workflow and passing `--target-url`, `--api-base-url`, `--target-db-url`, and `--checks full`.

Seed demo runs:

```bash
curl -X POST http://localhost:8000/demo/seed
```

The dashboard also exposes a **Seed Demo Runs** button. It creates three walkthrough runs that show ghost completion, contract drift, and state blindness using persisted JSON run records and reports.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Docker:

```bash
docker compose up --build
```

Planner mode:

```bash
PROOFMODE_PLANNER_MODE=llm
```

The LLM planner path uses a local heuristic provider by default, which lets the planner consume Git diff context without requiring API keys. To call OpenAI through the provider abstraction:

```bash
PROOFMODE_PLANNER_MODE=llm
PROOFMODE_LLM_PROVIDER=openai
PROOFMODE_LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=...
```

If provider output is invalid or unavailable, ProofMode falls back to the deterministic checklist and records that fallback in the run timeline.
The dashboard also shows a Planner Explainability panel for each run, including provider, model, diff files read, truncation, fallback status, and influenced files.

Runtime status:

```bash
curl http://localhost:8000/settings/status
```

The dashboard shows this as compact status chips for backend connectivity, planner mode, LLM provider, API key presence, and run persistence.

Targeted check assertions:

Planned checks may include an `assertions` object. Verifiers use this to run more specific checks:

- API: `method`, `path`, `expected_status`, `required_fields`
- UI: `text`, `selector`, `visible`, `url_contains`
- DB: `table`, `column`, `expected_row_delta`

## MVP Roadmap

- Checkpoint 1: Project skeleton and proof report contract
- Checkpoint 2: Playwright UI verifier with screenshots and console/network errors
- Checkpoint 3: HTTP API contract verifier
- Checkpoint 4: Database state verifier
- Checkpoint 5: Git diff analyzer and verification planner
- Checkpoint 6: Polished report dashboard

See `docs/ROADMAP.md` for the merged roadmap we are using, including the product structure inspired by the additional architecture plan.

See `docs/CHECKPOINTS.md` for the detailed 16-checkpoint implementation guide.
