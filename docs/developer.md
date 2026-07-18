# ScholarBridge Developer Guide

Use this checklist after making project changes and before attempting deployment.

## Prerequisites

- Python 3.11+
- `uv`
- A local `.venv`
- A configured `.env`
- Access to the local development database referenced by `.env` or `DATABASE_URL`

Initial setup:

```bash
cp .env.example .env
uv venv
uv sync
```

Update `.env` for your local database and secret settings before running the app.

## Local Validation Scripts

The local workflow scripts live under `scripts/`:

- `scripts/run_tests.sh`
  - activates `.venv`
  - runs `uv run pytest`
  - runs `git diff --check`
- `scripts/start_local_dev.sh`
  - verifies `.venv` exists
  - activates `.venv`
  - runs `uv run flask --app run.py db upgrade`
  - starts the Flask development server at `http://127.0.0.1:5000`
- `scripts/dev_cycle.sh`
  - activates `.venv`
  - prints `git status --short`
  - runs the test suite
  - runs the whitespace check
  - starts the Flask development server

## Required Pre-Deployment Exercise

Before deployment, a developer should complete this local cycle from the repository root:

```bash
scripts/run_tests.sh
scripts/start_local_dev.sh
```

After `start_local_dev.sh` starts the server, exercise the affected application behavior in the browser at:

```text
http://127.0.0.1:5000
```

At minimum:

- Sign in with a suitable local test account.
- Open the routes changed by the work.
- Confirm the changed behavior works.
- Confirm adjacent existing behavior still works.
- Confirm no unexpected stack traces or request failures appear in the terminal.

For a single command that runs status, tests, whitespace checks, and then starts the development server, use:

```bash
scripts/dev_cycle.sh
```

## Database Migrations

`scripts/start_local_dev.sh` runs:

```bash
uv run flask --app run.py db upgrade
```

This updates only the local development database. It does not update CI, staging, or production databases.

If a change includes migrations or model/schema changes, confirm locally that:

```bash
uv run flask --app run.py db current
uv run flask --app run.py db heads
```

report the expected revision state after `db upgrade`.

## Deployment Gate

Do not deploy until all of the following are true:

- `scripts/run_tests.sh` passes.
- `git diff --check` passes.
- The local server starts through `scripts/start_local_dev.sh` or `scripts/dev_cycle.sh`.
- The changed routes or workflows have been manually exercised in the browser.
- Any schema-changing deployment has a planned production migration step.

Production migration details are documented in `docs/deployment/cicd.md`.
