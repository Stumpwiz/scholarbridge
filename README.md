# ScholarBridge

ScholarBridge is a lightweight donor solicitation management CRM for the Example Scholarship Committee. It is being designed as a long-lived institutional tool to support consistent solicitation management, accurate records, and reliable committee handoff across years.

This project evolves from an Excel-centered process that has served the committee for years. The goal is not to discard that practice, but to preserve its practical strengths while reducing manual friction, improving traceability, and creating a stable operational baseline for future committee members.

## Purpose

ScholarBridge is intended to help the committee manage:

- Partners and associated contacts
- Campaign planning and solicitation tracking
- Donation tracking and follow-up
- Acknowledgment and correspondence workflows
- Historical reporting across years

## Design Priorities

- Institutional continuity over individual preference
- Clear solicitation management lifecycle tracking
- Low operational complexity for non-technical users
- Incremental migration from spreadsheet habits to structured workflows
- Compatibility with current local deployment and future platform growth

## Deployment Context (Initial)

- Local Apache-hosted Flask application on Windows 11
- Development on Ubuntu ARM64 (Development Host) using PyCharm
- Future Linux deployment compatibility expected from the outset

## Current Repository Stage

This repository is now in **Phase 2B.1: Solicitation workflow refinement**.

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

- Foundational SQLAlchemy models for `Person`, `User`, and `Partner`
- Flask-Login `user_loader` wired to `User` model lookup
- Minimal Partner workflow:
  - list
  - detail
  - create
  - edit

Still deferred:

- Campaign and Solicitation models/workflows
- Reporting, letter generation, imports, and automation

## Phase 1C Additions

Included:

- `Contact` SQLAlchemy model with partner-bound ownership
- Partner-to-Contact relationship (`Partner` 1-to-many `Contact`)
- Embedded contact workflow on partner detail pages:
  - view contacts
  - add contact
  - edit contact
- Optional/sparse contact fields preserved for low-friction solicitation management entry

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

## Phase 2B Additions

Included:

- `Solicitation` SQLAlchemy model
  - relationships: Partner 1-to-many Solicitation, Campaign 1-to-many Solicitation
  - fields: `partner_id`, `campaign_id`, `tranche`, `business_volume`,
    `amount_requested`, `amount_received`, `status`, `notes`, timestamps
  - conceptual uniqueness guardrail: one solicitation per partner per campaign
- Solicitation workflow pages:
  - list
  - detail
  - create
  - edit
- Controlled solicitation vocabularies:
  - tranche: `1`, `2`, `3`
  - status: `not_contacted`, `contacted`, `responded`, `donated`, `declined`, `closed`

Still deferred:

- Solicitation delete workflow
- Solicitor/MRPOC assignment fields and automation
- Authentication/authorization enforcement
- Reporting, analytics, letter generation, and automation

## Phase 2B.1 Workflow Refinements

Included:

- Solicitation create defaults and guardrails:
  - if exactly one active campaign exists, it is preselected
  - closed campaigns are excluded from new-solicitation campaign options
  - server-side validation blocks creation against closed campaigns
- Campaign-aware partner availability on solicitation create:
  - partner choices are filtered to unassigned partners for the selected campaign
  - uniqueness validation remains as final safeguard
- Campaign detail workspace evolution:
  - added Tranche 1/2/3 operational sections
  - each section lists campaign solicitations with partner, status, requested, and received amounts
  - partner links open solicitation detail as a primary campaign-management navigation path
- Navigation terminology update:
  - `Letter Generation` renamed to `Letters` (placeholder preserved)

Still deferred:

- Tranche reassignment workflows and drag/drop interfaces
- Kanban/charts/analytics dashboards
- Authorization enforcement and role-based UI restrictions

## Operational Refinements (Current)

Included:

- Partner mailing address fields:
  - `address_1`, `address_2`, `city`, `state`, `postal_code`
- Partner address capture/display in create/edit/detail workflows
- Contact delete workflow from partner detail page (POST-only)
- Ecosystem action-icon harmonization with Bootstrap Icons:
  - pencil for edit actions
  - trashcan for contact delete in compact contact lists
- Bootstrap importer updates:
  - maps mailing-address data from `vendors.xlsx` into Partner records
  - conservatively backfills missing address/email/phone fields for existing matched partners

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

4. Initialize or upgrade the database schema:

```bash
uv run flask --app run.py init-db
```

Equivalent Alembic commands:

```bash
uv run flask --app run.py db upgrade
```

Create a new migration after model changes:

```bash
uv run flask --app run.py db migrate -m "describe change"
uv run flask --app run.py db upgrade
```

For an existing SQLite database that predates Alembic and must be preserved, stamp it to the
baseline revision once, then run upgrades:

```bash
uv run flask --app run.py db stamp f96fd0b1ba49
uv run flask --app run.py db upgrade
```

Default local URL:

- `http://127.0.0.1:5000/`

Useful scaffold routes:

- Landing page: `/`
- Health: `/health`
- Auth status placeholder: `/auth/status`
- Partners: `/partners`
- Campaigns: `/campaigns`
- Solicitations: `/solicitations`

## Bootstrap Vendor Import (Temporary)

Use the one-time bootstrap importer to populate Partners and Contacts from the legacy vendor workbook.

Default import (non-destructive):

```bash
uv run python scripts/import_vendors.py
```

Reset Partners/Contacts first:

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

- Imports Partners and Contacts only.
- `--reset` deletes Contacts first, then Partners.
- Campaigns, Users, and Persons are preserved.
- Uses conservative normalization and exact-match dedupe only.
- Partner mailing-address fields are imported when present.
- Not intended as a generalized ETL/import framework.

## People Seed Export/Import (Development Utility)

Use these scripts to preserve `Person` records across SQLite rebuilds.

Export People to seed JSON:

```bash
uv run python scripts/export_people.py
```

Import People from seed JSON:

```bash
uv run python scripts/import_people.py
```

Seed file path:

- `data/seeds/people.json`

Scope notes:

- Exports/imports `Person` records only.
- Does not include Users, Campaigns, Solicitations, Partners, or Contacts.

## Partner Seed Export/Import (Development Utility)

Use these scripts to preserve curated `Partner` records across SQLite rebuilds.

Export Partners to seed JSON:

```bash
uv run python scripts/export_partners.py
```

Import Partners from seed JSON:

```bash
uv run python scripts/import_partners.py
```

Seed file path:

- `data/seeds/partners.json`

Scope notes:

- Exports/imports `Partner` records only.
- Does not include Campaigns, Solicitations, Contacts, Users, or Persons.

## Minimal Workflow

- Keep architecture documents current before adding feature code.
- Add remaining domain models and workflows incrementally in later phases.
- Use conservative, server-rendered workflows aligned with `docs/schema_v1.md` and `docs/ui_concepts.md`.
