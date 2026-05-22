# ScholarBridge

ScholarBridge is a lightweight donor stewardship CRM for the Example Scholarship Committee. It is being designed as a long-lived institutional tool to support consistent stewardship, accurate records, and reliable committee handoff across years.

This project evolves from an Excel-centered process that has served the committee for years. The goal is not to discard that practice, but to preserve its practical strengths while reducing manual friction, improving traceability, and creating a stable operational baseline for future committee members.

## Purpose

ScholarBridge is intended to help the committee manage:

- Organizations and associated contacts
- Campaign planning and solicitation tracking
- Donation tracking and follow-up
- Acknowledgment and correspondence workflows
- Historical reporting across years

## Design Priorities

- Institutional continuity over individual preference
- Clear stewardship lifecycle tracking
- Low operational complexity for non-technical users
- Incremental migration from spreadsheet habits to structured workflows
- Compatibility with current local deployment and future platform growth

## Deployment Context (Initial)

- Local Apache-hosted Flask application on Windows 11
- Development on Ubuntu ARM64 (Development Host) using PyCharm
- Future Linux deployment compatibility expected from the outset

## Current Repository Stage

This repository is now in **Phase 1B: foundational domain model implementation**.

Documentation remains the architectural source of truth, and the runtime foundation is now in place for conservative implementation phases.

## Phase 1A Scope

Included:

- Flask app factory and blueprint structure
- Configuration via `.env`
- Flask-SQLAlchemy and Flask-Login initialization
- Bootstrap-based base template and landing page
- Basic health route and authentication-status placeholder route

Deferred:

- CRUD workflows
- Campaign/solicitation business logic
- Reporting and PDF generation
- Spreadsheet import
- Advanced permissions and API layers

## Phase 1B Additions

Included:

- Foundational SQLAlchemy models for `Person`, `User`, and `Organization`
- Flask-Login `user_loader` wired to `User` model lookup
- Minimal Organization workflow:
  - list
  - detail
  - create
  - edit

Still deferred:

- Campaign, Solicitation, and Contact models/workflows
- Reporting, letter generation, imports, and automation

## Local Development (uv)

1. Create local environment file:

```bash
cp .env.example .env
```

2. Create a virtual environment and install dependencies:

```bash
uv venv
uv sync
```

3. Run the application:

```bash
uv run flask --app run.py run --debug
```

4. Initialize the database (first run or after schema changes):

```bash
uv run flask --app run.py init-db
```

Default local URL:

- `http://127.0.0.1:5000/`

Useful scaffold routes:

- Landing page: `/`
- Health: `/health`
- Auth status placeholder: `/auth/status`
- Organizations: `/organizations`

## Minimal Workflow

- Keep architecture documents current before adding feature code.
- Add remaining domain models and workflows incrementally in later phases.
- Use conservative, server-rendered workflows aligned with `docs/schema_v1.md` and `docs/ui_concepts.md`.
