# RESTART NOTES: ScholarBridge

This file provides resume context for future assistants and maintainers.

Current stage: **Phase 1C (Contact workflow implementation)**.

The project remains architecture-first. A minimal Flask runtime scaffold exists and the first conservative vertical slice (Organization) is now implemented.

## Project Snapshot

- Name: ScholarBridge
- Domain: Donor/patron CRM for the Example Scholarship Committee
- Goal: Institutional continuity, stewardship quality, and historical traceability
- Current operational baseline: legacy spreadsheet process

## Core Intent

ScholarBridge should evolve spreadsheet-era operations into a maintainable system without dismissing existing committee practices. The current phase establishes a conservative runtime foundation before domain workflows are built.

## Intended Stack (Planned, Not Yet Implemented)

- Flask
- SQLAlchemy
- SQLite (initially)
- Bootstrap
- Jinja2
- XeLaTeX (later, for PDF generation)

## Environment and Deployment Context

- Initial deployment target: local Apache-hosted Flask application on Windows 11
- Development machine: Ubuntu ARM64 ("Development Host") with PyCharm
- Design requirement: preserve future Linux deployment compatibility

## Stabilized Core Entities (Conceptual v1)

- Organization
- Contact
- Campaign
- Solicitation
- Person
- User

The stabilized conceptual schema is documented in `docs/schema_v1.md`.

Current conceptual relationship intent:

- Organization 1-to-many Contact
- Organization 1-to-many Solicitation
- Campaign 1-to-many Solicitation
- Person 1-to-many Solicitation
- User optional 1-to-1 Person

Canonical stewardship ownership:

- `Solicitation.assigned_person_id`

Stabilized conceptual decisions:

- Exactly one `Campaign` per `campaign_year` (conceptually unique year).
- One active campaign at a time is the normal operating model.
- `Campaign.campaign_name` follows a consistent format for reporting/exports: `"{campaign_year} Scholarship Campaign"` (example: `"2026 Scholarship Campaign"`).
- `Contact` remains strictly organization-bound; no standalone individual donors in v1.
- `Solicitation.primary_contact_id` remains optional in v1.
- Contact email/phone fields remain optional in v1 to support organization-only solicitation records.
- Stewardship ownership is person-based, not user-account-based.
- `User.email` is required and conceptually unique in v1.
- v1 assumes conventional local authentication only.
- `Campaign.status` vocabulary: `planned`, `active`, `closed`, `archived`.
- `Solicitation.status` vocabulary: `not_contacted`, `contacted`, `responded`, `donated`, `declined`, `closed`.
- Solicitation closure in v1 is tracked via `Solicitation.status` + `updated_at` (no `closed_at` field).
- Thank-you tracking in v1 is timestamp-based via `thank_you_sent_at`, which also serves donor acknowledgment/tax letter tracking in v1 (no separate `tax_letter_sent_at` field).

## Phase 1A Scaffold (Implemented)

Project structure added:

- `app/__init__.py` (app factory)
- `app/config.py` (environment-driven configuration)
- `app/extensions.py` (`SQLAlchemy`, `LoginManager`)
- `app/main/` blueprint (`/`, `/health`)
- `app/auth/` blueprint (`/auth/status` placeholder)
- `app/models/` placeholder package
- `app/templates/base.html` and `app/templates/index.html`
- `app/static/css/` and `app/static/js/` placeholders
- `run.py` app entrypoint + `flask init-db` command
- `instance/` directory for SQLite runtime artifacts

Current runtime behavior:

- App loads configuration from `.env` (with `.env.example` template).
- SQLite URI defaults to `instance/scholarbridge.db` via relative `DATABASE_URL=sqlite:///scholarbridge.db`.
- Flask-SQLAlchemy initializes cleanly.
- Flask-Login initializes with placeholder `user_loader` (no login workflows yet).
- Bootstrap navigation shell renders with v1-aligned placeholder sections.

Phase 1A deferrals:

- No CRUD/domain workflows
- No report generation
- No PDF/letter generation
- No import pipeline integration
- No model entities/migrations yet
- No authentication forms or permissions system

## Phase 1B Foundations (Implemented)

Model layer implemented:

- `Person` model (operational identity; optional User link)
- `User` model (local auth account; email/username unique; optional 1-to-1 Person)
- `Organization` model (long-term stewardship anchor)

Organization workflow implemented:

- Organization list page (`/organizations`)
- Organization detail page (`/organizations/<id>`)
- Organization create page (`/organizations/new`)
- Organization edit page (`/organizations/<id>/edit`)

Current constraints preserved:

- No Campaign model yet
- No Solicitation model yet
- No delete workflow for organizations
- No advanced auth workflows or permissions system
- No reporting, PDF generation, import, or email workflows

## Phase 1C Contact Workflow (Implemented)

Model layer additions:

- `Contact` model
  - organization-bound (`organization_id` required)
  - sparse-friendly fields (`first_name`, `last_name`, `title`, `email`, `phone`, `notes`)
  - stewardship flags (`is_primary`, `is_active`)
  - timestamps (`created_at`, `updated_at`)

Relationship additions:

- `Organization` now has many `Contact` records
- `Contact` belongs to exactly one `Organization`
- Organizations with zero contacts remain supported

Workflow additions:

- Embedded contacts section in organization detail page
  - list contacts
  - add contact
  - edit contact
- No contact delete workflow yet
- No standalone contact navigation/index/search workflow yet

Operational notes:

- Contact entry intentionally remains light: sparse/incomplete records are allowed.
- Minimal guardrail only: at least one identifying field (name/title/email/phone) is required to save.
- Marking a contact as primary automatically clears primary on other contacts within the same organization.

## Phase 0.5 Tooling Added

### Directory structure

- `data/original/` for manually copied source spreadsheets (not committed)
- `data/analysis/` for generated markdown profiling reports (not committed)
- `data/imports/` reserved for future import staging artifacts (not committed)
- `.gitkeep` files included to preserve folder structure in git

### Script

- `scripts/analyze_spreadsheet.py`

### Script behavior

- Uses pandas to load workbook and enumerate worksheet names
- Prints per-sheet column names and row counts
- Flags empty columns
- Flags likely duplicate rows
- Summarizes likely missing values
- Infers pragmatic field types heuristically
- Writes markdown profiling reports to `data/analysis/`
- Produces:
  - `<workbook_stem>_analysis.md`
  - `latest_analysis.md`

### Guardrails

- Non-destructive: does not modify spreadsheet data
- No automatic cleaning
- No database import
- No ORM generation
- No Flask/UI code generation

## Dependencies (Current Minimal)

See `pyproject.toml` / `requirements.txt`:

- Flask
- Flask-SQLAlchemy
- Flask-Login
- python-dotenv
- pandas
- openpyxl

## Guidance for Next Assistant

1. Treat `docs/schema_v1.md` and `docs/ui_concepts.md` as the implementation baseline unless committee policy changes.
2. Keep next phases conservative and server-rendered.
3. Add `Campaign` and `Solicitation` incrementally with migrations only when scope is agreed.
4. Preserve local Windows deployment compatibility and Linux portability when adding runtime behavior.
