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

## Test Scenarios

Run these claims against each project:

1. True claim: "The login page loads."
2. Unsupported claim: "The login flow is complete and tested."
3. UI claim: "The submit button works."
4. API claim: "The user endpoint still returns the expected fields."
5. DB claim: "The migration updated the users table."
6. Diff claim: "Only frontend files changed."

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
- connect Git diff risk to verification layers,
- generate a reusable report or evidence bundle.

## Current Limitation

ProofMode can check public or locally running targets, but a deployed ProofMode instance cannot directly reach a project running on a laptop `localhost`. For local projects, run the ProofMode CLI locally or expose the target app through a temporary tunnel.
