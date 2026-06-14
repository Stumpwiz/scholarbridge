# ScholarBridge CI/CD Deployment

This project uses GitHub Actions to run tests on every push/PR, then deploy to production only when a push to `main` passes tests.

## Design Summary

- Source of truth: GitHub `main`
- CI: `.github/workflows/tests.yml` (`test` job)
- CD: `.github/workflows/tests.yml` (`deploy` job, gated by `needs: test`)
- Transport: SSH + `rsync` to a staging directory, then server-side `rsync` into `/opt/scholarbridge`
- Service management: `systemd` (`scholarbridge.service`)
- Health check: `http://127.0.0.1:8000/health`
- Database migrations: manual only (not executed by deploy workflow)

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
   - `deploy` must pass
5. Validate on server:
   - `systemctl status scholarbridge.service`
   - `journalctl -u scholarbridge.service -n 100 --no-pager`
   - `curl http://127.0.0.1:8000/health`

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
