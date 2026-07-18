# ScholarBridge CI/CD Deployment

This project uses GitHub Actions to run tests on every push/PR, then deploy to production only when a push to `main` passes tests.

## Design Summary

- Source of truth: GitHub `main`
- CI: `.github/workflows/tests.yml` (`test` job)
- CD: `.github/workflows/tests.yml` (`deploy` job, gated by `needs: test`)
- Transport: SSH + `rsync` to a staging directory, then server-side `rsync` into `/opt/scholarbridge`
- Service management: `systemd` (`scholarbridge.service`)
- Health check: `http://127.0.0.1:8000/health`
- Database migrations: automatic during production deploy, before service restart

## Schema Changes and Production Migrations

### How to Recognize a Schema-Changing Deployment

Treat a deployment as schema-changing when a commit includes any of the following:

- new or updated files under `migrations/versions/`
- model changes that add/remove/rename columns or constraints
- code paths that reference newly added ORM attributes/columns

If any of these are present, confirm the deployment applied the production migration successfully before functional verification.

### Why GitHub Actions Migrations Do Not Update Production

GitHub Actions runs tests and migrations against CI job databases during the `test` job.
Those test-job migrations do **not** touch:

- local development database
- staging database (if separate)
- production database

CI success means application and migration code are valid in CI. Production migrations are applied later by the production `deploy` job after files are synced and before `scholarbridge.service` is restarted.

### CI vs Development vs Production Databases

- **CI database**: ephemeral database created inside the GitHub Actions job.
- **Development database**: your local machine DB used by `uv run ...` commands locally.
- **Production database**: the persistent DB used by `scholarbridge.service` on EC2.

Each environment must be migrated independently.

### Required Deployment Sequence for Schema Changes

Use this sequence for every schema-changing release:

1. commit
2. push
3. CI/CD deploy
4. automatic production `flask db upgrade`
5. automatic service restart
6. automatic health check
7. application verification

### Production Migration Procedure

The deployment workflow runs this procedure automatically on every production deployment after `uv sync --frozen` and before restarting Gunicorn:

```bash
cd /opt/scholarbridge
set -a
source /etc/scholarbridge/scholarbridge.env
set +a

uv run flask --app run.py db current
uv run flask --app run.py db heads
uv run flask --app run.py db upgrade

sudo systemctl restart scholarbridge.service
sudo systemctl status scholarbridge.service --no-pager
curl -i http://127.0.0.1:8000/health
```

`flask db upgrade` is idempotent. If the production database is already at Alembic HEAD, it exits successfully without changing the schema.

Use the same commands manually only for troubleshooting or one-off recovery.

### Environment File Distinction (Critical)

- `/etc/scholarbridge/scholarbridge.env`:
  - runtime environment used by the running `systemd` service (`EnvironmentFile=...`)
  - must be sourced for production migration commands to target the same DB as the service
- `/opt/scholarbridge/.env`:
  - local/app-shell convenience file
  - may point to a different database than the running service

Troubleshooting lesson: when migration commands and service process use different env files, you can migrate the wrong database and still get missing-column failures in production.

### Troubleshooting: Missing-Column Failures After Deploy

Symptoms often include:

- `sqlalchemy.exc.ProgrammingError`
- `psycopg.errors.UndefinedColumn`
- immediate failures on routes that read/write new fields

Checklist:

1. Confirm active revision in production:
   - `uv run flask --app run.py db current`
2. Confirm expected head revision:
   - `uv run flask --app run.py db heads`
3. If current != head, inspect the failed deployment log, then run if needed:
   - `uv run flask --app run.py db upgrade`
4. Restart service and re-check health:
   - `sudo systemctl restart scholarbridge.service`
   - `curl -i http://127.0.0.1:8000/health`
5. If DB authentication errors occur, verify env source:
   - ensure `/etc/scholarbridge/scholarbridge.env` is loaded before migration commands

### Reusable Case Study: Schema and Code Drift

Operational pattern to remember:

1. code deployment succeeds
2. production migration runs automatically before restart
3. service restarts only after migration succeeds
4. health check verifies the restarted service

Use this pattern as a standard incident-response path for future schema releases.

## Why This Approach

`/opt/scholarbridge` is currently a non-Git runtime directory. SSH + `rsync` is the safest incremental deployment model because it:

- works with current server layout without migration risk
- supports deletions with `--delete` for clean code updates
- preserves production-only assets via explicit excludes
- requires no production secrets in GitHub other than SSH connection material

## Required GitHub Secrets

Create these repository secrets:

- `SCHOLARBRIDGE_PROD_SSH_HOST`: production host/IP
- `SCHOLARBRIDGE_PROD_SSH_USER`: SSH user with sudo rights (or equivalent deploy rights)
- `SCHOLARBRIDGE_PROD_SSH_PORT`: SSH port (usually `22`)
- `SCHOLARBRIDGE_PROD_SSH_PRIVATE_KEY`: private key for the deploy user
- `SCHOLARBRIDGE_PROD_SSH_KNOWN_HOSTS`: pinned known_hosts line(s) for the production host

## AWS-Side Preparation

1. Ensure deploy user can SSH from GitHub Actions key and run:
   - `sudo rsync`
   - `sudo systemctl restart scholarbridge.service`
   - `sudo systemctl is-active scholarbridge.service`
   without password prompts.
2. Ensure app runtime user exists (`scholarbridge`) and owns `/opt/scholarbridge`.
3. Ensure `uv` is available to the app user (`$HOME/.local/bin/uv` or `/usr/local/bin/uv`).
4. Ensure service unit exists and is enabled: `scholarbridge.service`.
5. Ensure health endpoint is reachable locally: `curl http://127.0.0.1:8000/health`.

## Production-Only Asset Protection

`deploy/rsync-exclude.txt` prevents overwrite/deletion of:

- `.env` and `.env.*`
- `docs/private/`
- `instance/` (generated letters and runtime artifacts)
- `generated_letters/` (if configured outside `instance/`)
- `logs/`
- `app/static/img/avatars/uploads/`

Adjust excludes if your generated artifacts are stored elsewhere.

## First Deployment Procedure

1. Add the required GitHub secrets.
2. Confirm production server prep items above.
3. Merge this CI/CD change to `main`.
4. Push a trivial commit to `main` and watch Actions:
   - `test` must pass
   - `deploy` must pass, including the production migration step
5. Validate on server:
   - `systemctl status scholarbridge.service`
   - `journalctl -u scholarbridge.service -n 100 --no-pager`
   - `curl http://127.0.0.1:8000/health`
6. If deployment includes schema changes, confirm production is at Alembic HEAD before functional verification.

## Rollback

Because this model syncs files into a single runtime directory, rollback is commit-based:

1. Re-run deployment from a known-good commit by reverting/cherry-picking on `main`.
2. Push to `main`.
3. Actions deploys that code and restarts the service.

For faster emergency rollback, keep server-side tar snapshots before deploy (optional future improvement).

## Git Checkout Evaluation

### Feasible?

Yes, feasible with a one-time migration.

### Benefits

- straightforward rollbacks (`git checkout <tag|commit>`)
- easier provenance and auditability on server
- simpler diffs/debugging during incidents

### Risks/Requirements

- production-only assets must move outside repo (for example `/var/lib/scholarbridge/private/`) and be mounted/symlinked
- writable runtime directories (`instance`, uploads, logs) should be externalized
- ownership/permissions and operational runbooks need updates

### Recommendation

- **Now:** keep non-Git `rsync` deployment (implemented here) for low-risk adoption.
- **Next phase:** migrate to Git checkout with externalized mutable/private paths for better rollback ergonomics.

## Security Notes

- Keep private key scope minimal and rotate periodically.
- Use pinned `known_hosts`; do not disable host key checking.
- Use GitHub Environment protection (`production`) with required reviewers if desired.
- Do not store DB credentials or app secrets in GitHub; keep them on server (`/etc/scholarbridge/scholarbridge.env`).
