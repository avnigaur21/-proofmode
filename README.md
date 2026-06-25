# ProofMode

ProofMode is an AI agent verification layer. It intercepts a "task complete" claim and demands proof across UI behavior, API contracts, data state, and code diffs before the claim is treated as true.

This repository starts with the smallest useful version of that idea:

- a FastAPI backend that accepts verification runs
- a React + Vite dashboard that displays run status
- verifier modules for UI, API, DB, and Git diff checks
- an approval gate for accepting, rejecting, or requesting fixes after review
- demo scenarios for ghost completion, contract drift, and state blindness
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

## MVP Roadmap

- Checkpoint 1: Project skeleton and proof report contract
- Checkpoint 2: Playwright UI verifier with screenshots and console/network errors
- Checkpoint 3: HTTP API contract verifier
- Checkpoint 4: Database state verifier
- Checkpoint 5: Git diff analyzer and verification planner
- Checkpoint 6: Polished report dashboard

See `docs/ROADMAP.md` for the merged roadmap we are using, including the product structure inspired by the additional architecture plan.

See `docs/CHECKPOINTS.md` for the detailed 16-checkpoint implementation guide.
