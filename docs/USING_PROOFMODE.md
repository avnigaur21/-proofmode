# Using ProofMode On Another Project

This guide is for validating ProofMode against a real local project.

## One-Time CLI Setup

From the ProofMode backend folder:

```bash
cd backend
pip install -e .
```

After that, you can run ProofMode as `proofmode verify ...` instead of `python -m app.cli verify ...`.

## Diff-Only First Pass

Use this when the target project is a Git repository but the app is not running.

```bash
proofmode verify \
  --claim "Agent says the feature is complete" \
  --agent-report "I changed the files and verified the implementation" \
  --checks diff \
  --repo-path C:\path\to\other\project \
  --source manual \
  --agent-name Avni
```

Review:

- changed-file classification
- recommended proof layers
- evidence verdict
- agent report vs evidence
- generated Markdown report

## UI Pass

Start the target frontend first, then run:

```bash
proofmode verify \
  --claim "Agent says the page renders correctly" \
  --agent-report "I opened the page and checked it visually" \
  --checks ui \
  --target-url http://localhost:5173
```

## API Pass

Start the target backend first, then run:

```bash
proofmode verify \
  --claim "Agent says the API is working" \
  --agent-report "I checked the health endpoint" \
  --checks api \
  --api-base-url http://localhost:8000/health
```

## Test Evidence Pass

Use this when the agent claims it ran tests:

```bash
proofmode verify \
  --claim "Agent says the test suite passes" \
  --agent-report "I ran the tests and they passed" \
  --checks tests \
  --repo-path C:\path\to\other\project \
  --test-command "Pytest=pytest tests"
```

ProofMode records the command, exit code, duration, stdout, and stderr. If the command fails or times out, the proof fails.

## What To Learn

After each run, inspect `proofmode-runs/` and the dashboard. The goal is to understand where ProofMode has strong evidence and where it still needs better proof capture.
