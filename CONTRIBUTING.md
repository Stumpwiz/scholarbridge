# Contributing

Thanks for contributing to ScholarBridge.

## Development Setup

```bash
uv venv
uv sync
cp .env.example .env
uv run flask --app run.py init-db
```

Run tests before submitting:

```bash
PYTHONPATH=. uv run python -m pytest
```

## Pull Request Expectations

- Keep changes scoped to the stated objective.
- Add or update tests when behavior changes.
- Update documentation for user-facing or operational changes.
- Do not include unrelated refactors.

## Data and Security Requirements

- Commit only synthetic seed data and fixtures.
- Do not commit real names, emails, phone numbers, addresses, donor data, partner data, or production exports.
- Do not commit credentials, private keys, tokens, dumps, or local environment files.

See:

- `docs/open-source/DATA_POLICY.md`
- `SECURITY.md`
- `docs/open-source/RELEASE_CHECKLIST.md`
