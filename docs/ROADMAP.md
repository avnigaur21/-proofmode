# ProofMode Roadmap

This roadmap combines the original ProofMode vision with the stronger architecture details from the second plan.

## Product Concept

ProofMode verifies an AI coding agent's "done" claim before humans trust it. A task is not complete just because the agent says it is complete. ProofMode asks for evidence.

## Core Objects

- Task: the original request or claim that needs verification.
- Verification run: one execution of ProofMode against a task.
- Checklist: the planned checks across UI, API, data, and code diff.
- Evidence: screenshots, console errors, network errors, API snapshots, DB snapshots, changed files, and report files.
- Approval: the human decision after reviewing the proof report.

## MVP Must Ship

1. UI verification with Playwright.
2. API contract snapshot and diff.
3. Git diff analysis.
4. Markdown proof report.
5. Approval gate: accept, reject, or request fix.
6. Dashboard and task detail view.
7. Seed demo tasks that show ghost completion, silent breakage, and contract drift.

## Add If Time Allows

1. Database snapshot and diff.
2. Screenshot before/after slider.
3. Re-run verification after fixes.
4. Async workers for long-running checks.

## Leave For V2

1. Native MCP integration.
2. CI/CD webhook triggers.
3. Multi-project support.
4. Enterprise authentication and audit controls.

## Build Phases

For the detailed implementation checklist, see `docs/CHECKPOINTS.md`.

### Phase 1: Foundation

- FastAPI app structure.
- React dashboard structure.
- Shared proof report contract.
- Placeholder verifiers for UI, API, DB, and Git diff.
- Local generated output folders.

### Phase 2: Verification Planner

- Deterministic planner first.
- LLM planner later.
- Planner returns structured JSON:
  - `ui_checks`
  - `api_checks`
  - `data_checks`
  - `affected_files_hint`

### Phase 3: L1 UI Verifier

- Open target URL.
- Capture screenshots.
- Detect console errors.
- Detect failed network requests.
- Check element existence, visibility, clickability, and text presence.

### Phase 4: L2 API Verifier

- Call endpoints.
- Capture status codes.
- Extract response schemas.
- Compare before and after snapshots.
- Report removed endpoints, status changes, and schema changes.

### Phase 5: Git Diff Analyzer

- Read changed files.
- Categorize frontend, backend, API, DB, and shared logic changes.
- Recommend verification layers based on changed areas.

### Phase 6: L3 Data Verifier

- Snapshot table counts.
- Snapshot schema metadata.
- Capture limited sample rows.
- Compare before and after state.

### Phase 7: Approval Gate

- Human accepts proof.
- Human rejects proof.
- Human requests a fix with instructions.

## Important Architecture Decision

We will keep generated run artifacts under `proofmode-runs/` instead of `proof_runs/`.

Reason: it reads more clearly as an application-owned artifact folder and already exists in the scaffold. The purpose is the same:

```txt
proofmode-runs/
  run-id/
    before.png
    after.png
    api_snapshot_before.json
    api_snapshot_after.json
    db_snapshot_before.json
    db_snapshot_after.json
    report.md
```
