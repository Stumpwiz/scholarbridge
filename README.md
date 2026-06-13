# ScholarBridge

ScholarBridge is a lightweight campaign and solicitation management application for committee-based fundraising workflows. It is designed for long-term continuity, clear recordkeeping, and practical day-to-day use.

## Features

- Partner and contact management
- Annual campaign tracking
- Solicitation workflow and status tracking
- Letter generation pipeline
- PostgreSQL-first runtime with migrations

## Requirements

- Python 3.11+
- `uv` (recommended package/runtime manager)
- PostgreSQL (local development)

## Installation

```bash
git clone <your-fork-or-repo-url>
cd scholarbridge
cp .env.example .env
uv venv
uv sync
```

## Local Development

1. Configure local database settings in `.env`.
2. Apply database migrations:

```bash
uv run flask --app run.py init-db
```

3. Start the app:

```bash
uv run flask --app run.py run --debug
```

## Testing

```bash
PYTHONPATH=. uv run python -m pytest
```

## Deployment Overview

ScholarBridge can be deployed using a standard Flask stack:

- Gunicorn application server
- Nginx reverse proxy
- PostgreSQL database
- Systemd service management

Reference deployment templates live under `deploy/` and `docs/deployment/`.

## Seed Data Policy

All committed seed fixtures must be synthetic. Do not commit:

- real names
- real email addresses
- real phone numbers
- real mailing addresses
- real donor or partner records
- production exports
- personal images

See `data/seeds/README.md` and `docs/open-source/DATA_POLICY.md`.

## Open Source Governance

- Contributing guide: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
- Code of conduct: `CODE_OF_CONDUCT.md`
- License: `LICENSE` (Apache-2.0)
- Release checklist: `docs/open-source/RELEASE_CHECKLIST.md`

## Security Reporting

Please report suspected vulnerabilities according to `SECURITY.md`. Do not open public issues for unpatched vulnerabilities.
