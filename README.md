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

This repository is now in **Phase 1D: Campaign foundation implementation**.

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

- Campaign and Solicitation models/workflows
- Reporting, letter generation, imports, and automation

## Phase 1C Additions

Included:

- `Contact` SQLAlchemy model with organization-bound ownership
- Organization-to-Contact relationship (`Organization` 1-to-many `Contact`)
- Embedded contact workflow on organization detail pages:
  - view contacts
  - add contact
  - edit contact
- Optional/sparse contact fields preserved for low-friction stewardship entry

Still deferred:

- Contact delete workflow
- Standalone contact index/search/filter pages
- Communication timeline/history and CRM-style activity logging

## Phase 1D Additions

Included:

- `Campaign` SQLAlchemy model
  - fields: `campaign_year`, `campaign_name`, `status`, `notes`, timestamps
  - one campaign per year enforced via unique `campaign_year`
- Campaign workflow pages:
  - list
  - detail
  - create
  - edit
- Campaign status vocabulary implemented:
  - `planned`
  - `active`
  - `closed`
  - `archived`
- Campaign naming convention enforced in app logic:
  - `"{campaign_year} Scholarship Campaign"`
- Lightweight one-active-campaign convention notices (warning when multiple are active)

Still deferred:

- Campaign delete workflow
- Solicitation workflows and campaign-linked operational analytics
- Reports, letter generation, imports, and automation

## Operational Refinements (Current)

Included:

- Organization mailing address fields:
  - `address_1`, `address_2`, `city`, `state`, `postal_code`
- Organization address capture/display in create/edit/detail workflows
- Contact delete workflow from organization detail page (POST-only)
- Ecosystem action-icon harmonization with Bootstrap Icons:
  - pencil for edit actions
  - trashcan for contact delete in compact contact lists
- Bootstrap importer updates:
  - maps mailing-address data from `vendors.xlsx` into Organization records
  - conservatively backfills missing address/email/phone fields for existing matched organizations

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

For local SQLite upgrades where new columns were added (for example organization mailing-address fields),
rebuild the local database file before re-running `init-db`.

Default local URL:

- `http://127.0.0.1:5000/`

Useful scaffold routes:

- Landing page: `/`
- Health: `/health`
- Auth status placeholder: `/auth/status`
- Organizations: `/organizations`
- Campaigns: `/campaigns`

## Bootstrap Vendor Import (Temporary)

Use the one-time bootstrap importer to populate Organizations and Contacts from the legacy vendor workbook.

Default import (non-destructive):

```bash
uv run python scripts/import_vendors.py
```

Reset Organizations/Contacts first:

```bash
uv run python scripts/import_vendors.py --reset
```

Explicit workbook path + reset:

```bash
uv run python scripts/import_vendors.py data/original/vendors.xlsx --reset
```

Dry-run analysis (no writes):

```bash
uv run python scripts/import_vendors.py --dry-run
```

Importer guardrails:

- Imports Organizations and Contacts only.
- `--reset` deletes Contacts first, then Organizations.
- Campaigns, Users, and Persons are preserved.
- Uses conservative normalization and exact-match dedupe only.
- Organization mailing-address fields are imported when present.
- Not intended as a generalized ETL/import framework.

## Minimal Workflow

- Keep architecture documents current before adding feature code.
- Add remaining domain models and workflows incrementally in later phases.
- Use conservative, server-rendered workflows aligned with `docs/schema_v1.md` and `docs/ui_concepts.md`.
