# Next ProofMode Checkpoints

These are the highest-value next checkpoints after claim ingestion, CLI mode, PR integration, evidence bundles, and self-report comparison.

## 1. Test Evidence Capture

Add a `--test-command` option so ProofMode can independently run and store test evidence.

Expected evidence:

- command
- exit code
- stdout
- stderr
- duration
- pass/fail status

## 2. Dashboard Bundle Download

Add a run detail button for downloading:

```txt
/artifacts/bundles/<run-id>
```

## 3. Full PR Verification Presets

Create documented GitHub Actions presets for:

- diff-only
- API verification
- UI verification
- DB verification
- full verification

## 4. Project-Level Policies

Let saved projects define required proof behavior:

- required layers
- required test command
- fail on self-report mismatch
- approval requirement
- minimum verdict

## 5. Stronger Self-Report Parsing

Add optional LLM parsing for structured self-report claims while keeping the deterministic fallback.
