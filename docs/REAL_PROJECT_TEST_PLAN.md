# Testing ProofMode on Real Projects

This plan is for validating ProofMode against real codebases instead of only demo runs.

## Goal

Use ProofMode on two or three existing projects and record whether it can catch unsupported agent claims, missing verification, broken UI flows, API drift, database uncertainty, or risky Git diffs.

## Project Selection

Start with these project types:

1. A React app with visible user flows, such as login, dashboard, forms, or navigation.
2. A backend/API project with health, auth, user, or data endpoints.
3. A full-stack project with a database or migrations.

Avoid production databases at first. Use local SQLite, local Postgres, or seeded test data.

## Setup Per Project

Create one ProofMode project profile per target project:

- `repo_path`: local path to the Git repository.
- `target_url`: running frontend URL.
- `api_base_url`: API base URL.
- `target_db_url`: test database URL when available.
- enabled checks: start with UI + API + Git diff, then add DB after the test DB is safe.
- `api_checks`: reusable endpoint checks.
- `ui_flows`: reusable browser flow checks.
- `test_commands`: reusable commands such as unit tests, backend tests, or frontend builds.

Example API checks:

```json
[
  {
    "name": "Health endpoint",
    "method": "GET",
    "path": "/health",
    "expected_status": 200,
    "required_fields": ["status"]
  }
]
```

Example UI flow:

```json
[
  {
    "name": "Login page smoke",
    "path": "/login",
    "steps": [
      { "action": "expect_selector", "selector": "form" },
      { "action": "expect_text", "text": "Login" }
    ]
  }
]
```

Example test commands:

```json
[
  {
    "name": "Backend tests",
    "command": "pytest tests",
    "timeout_seconds": 120
  },
  {
    "name": "Frontend build",
    "command": "npm run build",
    "working_directory": "C:\\path\\to\\project\\frontend",
    "timeout_seconds": 180
  }
]
```

## Test Scenarios

Run these claims against each project:

1. True claim: "The login page loads."
2. Unsupported claim: "The login flow is complete and tested."
3. UI claim: "The submit button works."
4. API claim: "The user endpoint still returns the expected fields."
5. DB claim: "The migration updated the users table."
6. Diff claim: "Only frontend files changed."
7. Test claim: "I ran the test suite and it passed."

## What To Record

For each run, save:

- claim text
- agent self-report
- final ProofMode status
- evidence evaluator verdict
- failed or uncertain checks
- screenshot/report/bundle path
- whether ProofMode found something useful

## Success Criteria

ProofMode is useful if it can:

- identify when an agent claims more than it proved,
- produce evidence a human can review,
- flag missing UI/API/DB proof as insufficient,
- support or contradict "I ran tests" using actual command output,
- connect Git diff risk to verification layers,
- generate a reusable report or evidence bundle.

## Current Limitation

ProofMode can check public or locally running targets, but a deployed ProofMode instance cannot directly reach a project running on a laptop `localhost`. For local projects, run the ProofMode CLI locally or expose the target app through a temporary tunnel.
