# RESTART NOTES: ScholarBridge

This file provides resume context for future assistants and maintainers.

Current stage: **Phase 2D.1 (Partner category realignment)**.

The project remains architecture-first. A minimal Flask runtime scaffold exists and the first conservative vertical slice (Partner) is now implemented.

## Project Snapshot

- Name: ScholarBridge
- Domain: Donor/patron CRM for the Example Scholarship Committee
- Goal: Institutional continuity, solicitation management quality, and historical traceability
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

- Partner
- Contact
- Campaign
- Solicitation
- Person
- User

The stabilized conceptual schema is documented in `docs/schema_v1.md`.

Current conceptual relationship intent:

- Partner 1-to-many Contact
- Partner 1-to-many Solicitation
- Campaign 1-to-many Solicitation
- Campaign 1-to-many CampaignCategoryMRPOC
- Person 1-to-many Solicitation (as solicitor)
- Person 1-to-many Solicitation (as MRPOC)
- Person 1-to-many CampaignCategoryMRPOC (as MRPOC)
- User optional 1-to-1 Person

Stabilized conceptual decisions:

- Exactly one `Campaign` per `campaign_year` (conceptually unique year).
- One active campaign at a time is the normal operating model.
- `Campaign.campaign_name` follows a consistent format for reporting/exports: `"{campaign_year} Scholarship Campaign"` (example: `"2026 Scholarship Campaign"`).
- `Contact` remains strictly partner-bound; no standalone individual donors in v1.
- Contact email/phone fields remain optional in v1 to support partner-only solicitation records.
- `User.email` is required and conceptually unique in v1.
- v1 assumes conventional local authentication only.
- `Campaign.status` vocabulary: `planned`, `active`, `closed`, `archived`.
- `Solicitation.status` vocabulary: `not_contacted`, `contacted`, `responded`, `donated`, `declined`, `closed`.
- `Solicitation.tranche` vocabulary: `1`, `2`, `3`.
- One `Solicitation` per Partner+Campaign is a core v1 guardrail.
- Solicitation closure in v1 is tracked via `Solicitation.status` + `updated_at` (no `closed_at` field).
- Solicitation phase-2C includes `solicitor_person_id` (Person-based assignment).
- Solicitation phase-2D includes optional `mrpoc_person_id` (Person-based correspondence context).
- Campaign phase-2D includes category-to-MRPOC mapping per campaign year.
- Canonical partner category vocabulary (phase 2D.1):
  - Food and Beverage
  - Finance
  - Insurance
  - Accounting
  - HR
  - IT
  - Security Services
  - Construction
  - Renovation
  - Moving
  - Packing
  - Medical Service Providers
  - Personal Service Providers
  - Cleaning Services and Supplies
  - Admin
- Temporary review category in app workflows: `Needs Review`.
- Solicitation create workflow in phase 2B.1 excludes closed campaigns and preselects campaign when exactly one is active.
- Solicitation create partner options in phase 2B.1 are campaign-aware (unassigned partners only).

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
- `Partner` model (long-term solicitation management anchor)

Partner workflow implemented:

- Partner list page (`/partners`)
- Partner detail page (`/partners/<id>`)
- Partner create page (`/partners/new`)
- Partner edit page (`/partners/<id>/edit`)

Current constraints preserved:

- No delete workflow for partners
- No advanced auth workflows or permissions system
- No reporting, PDF generation, import, or email workflows

## Phase 1C Contact Workflow (Implemented)

Model layer additions:

- `Contact` model
  - partner-bound (`partner_id` required)
  - sparse-friendly fields (`first_name`, `last_name`, `title`, `email`, `phone`, `notes`)
  - solicitation management flags (`is_primary`, `is_active`)
  - timestamps (`created_at`, `updated_at`)

Relationship additions:

- `Partner` now has many `Contact` records
- `Contact` belongs to exactly one `Partner`
- Partners with zero contacts remain supported

Workflow additions:

- Embedded contacts section in partner detail page
  - list contacts
  - add contact
  - edit contact
- No contact delete workflow yet
- No standalone contact navigation/index/search workflow yet

Operational notes:

- Contact entry intentionally remains light: sparse/incomplete records are allowed.
- Minimal guardrail only: at least one identifying field (name/title/email/phone) is required to save.
- Marking a contact as primary automatically clears primary on other contacts within the same partner.

## Phase 1D Campaign Foundation (Implemented)

Model layer additions:

- `Campaign` model
  - `campaign_year` (required, unique)
  - `campaign_name` (required, convention-based)
  - `status` (`planned`, `active`, `closed`, `archived`)
  - `notes` (optional)
  - timestamps (`created_at`, `updated_at`)

Workflow additions:

- Campaign list page (`/campaigns`)
- Campaign detail page (`/campaigns/<id>`)
- Campaign create page (`/campaigns/new`)
- Campaign edit page (`/campaigns/<id>/edit`)
- No campaign delete workflow yet

Operational notes:

- Campaign names are generated from year using:
  - `"{campaign_year} Scholarship Campaign"`
- One active campaign at a time remains a convention, not a hard block.
- UI warns when multiple campaigns are marked active.

## Phase 2B Solicitation Foundation (Implemented)

Model layer additions:

- `Solicitation` model
  - required relationships: `partner_id`, `campaign_id`
  - controlled fields: `tranche`, `status`
  - dollar fields: `business_volume`, `amount_requested`, `amount_received`
  - optional notes + timestamps
  - uniqueness guardrail on `(partner_id, campaign_id)`

Workflow additions:

- Solicitation list page (`/solicitations`)
- Solicitation detail page (`/solicitations/<id>`)
- Solicitation create page (`/solicitations/new`)
- Solicitation edit page (`/solicitations/<id>/edit`)
- No solicitation delete workflow yet

Operational notes:

- Validation remains conservative and workflow-light.
- Partner/Campaign duplicate assignments are blocked.
- Correspondence timestamps remain deferred to later refinement phases.

## Phase 2B.1 Solicitation Workflow Refinement (Implemented)

Workflow additions:

- Solicitation create preselects campaign when exactly one active campaign exists.
- Closed campaigns are omitted from new-solicitation campaign options.
- Server-side validation blocks new solicitation creation for closed campaigns.
- Solicitation create partner options are filtered by selected campaign:
  - available partners = all partners minus already assigned partners in that campaign
- Campaign detail now includes tranche workspace sections:
  - Tranche 1
  - Tranche 2
  - Tranche 3
- Each tranche section lists solicitations with:
  - partner
  - status
  - amount requested
  - amount received
- Partner links in tranche sections navigate to solicitation detail records.

UI convention update:

- Navigation placeholder label changed from `Letter Generation` to `Letters`.

## Phase 2C Solicitor Assignment + Campaign Workbench (Implemented)

Model/workflow additions:

- `Solicitation` now supports optional `solicitor_person_id` referencing `Person`.
- Campaign detail now acts as an assignment workbench with an `Assign Partner to Tranche` flow.
- Assigning from campaign detail creates the solicitation record immediately and routes to solicitation edit.
- Existing one-partner-per-campaign guardrail is preserved.

UI/workflow refinements:

- Campaign tranche tables now show: Partner, Solicitor, Status, Amount Requested, Amount Received.
- Solicitation create/edit/detail/list now expose solicitor assignment.
- Solicitation list columns now include solicitor and are ordered by tranche then partner.

## Phase 2C.5 Person Management (Implemented)

Model/workflow additions:

- Added lightweight People workflow:
  - list (`/people`)
  - create (`/people/new`)
  - edit (`/people/<id>/edit`)
- No person delete workflow (intentionally deferred for ownership continuity).
- Navigation now includes a user-facing `People` entry.

Person data refinements:

- `Person` now includes optional:
  - `middle_initial`
  - `mobile_phone`
  - `other_phone`
- Existing `preferred_name`, `committee_role`, and `person_notes` remain supported.
- Person forms remain sparse-data-friendly outside required name fields.

## Phase 2D MRPOC Assignment + Campaign Category Mapping (Implemented)

Model/workflow additions:

- Added `CampaignCategoryMRPOC` model:
  - `campaign_id`
  - `partner_category`
  - `mrpoc_person_id`
  - optional `notes`
  - timestamps
  - uniqueness guardrail on `(campaign_id, partner_category)`
- Added optional `Solicitation.mrpoc_person_id` referencing `Person`.

Workflow additions:

- Campaign detail/workbench now includes `MRPOC Mapping by Partner Category`.
- Mapping choices use the existing controlled partner category vocabulary.
- Solicitation creation from campaign workbench partner assignment now auto-assigns MRPOC:
  - if campaign+category mapping exists, copy mapped person into `Solicitation.mrpoc_person_id`
  - if no mapping exists, leave `mrpoc_person_id` blank
- Solicitation create/edit now allows manual MRPOC selection/override.
- Solicitation detail/list and campaign tranche tables now display MRPOC as secondary correspondence context.

Operational notes:

- MRPOC is informational/correspondence context, not operational ownership.
- Solicitor remains the operational owner.
- Missing mappings do not block solicitation creation.
- Bulk remapping and mid-campaign remap automation remain deferred.

## Phase 2D.1 Partner Category Realignment (Implemented)

Category alignment updates:

- Replaced legacy partner category options with the committee-approved canonical vocabulary.
- Introduced `Needs Review` as a temporary cleanup value for records with legacy/invalid categories.
- Existing partner records with non-canonical categories are automatically normalized to `Needs Review`.
- MRPOC campaign mapping choices now use canonical categories only.

Importer updates:

- Bootstrap importer no longer infers partner category from partner name keywords.
- Imported partners now default category to blank unless explicitly set later by committee review.

Operational notes:

- No automatic category guessing is performed in phase 2D.1.
- Category cleanup is intentionally manual and visible on the Partner list/edit workflows.

## Operational Refinements (Implemented)

Partner model/workflow:

- Added optional mailing-address fields:
  - `address_1`, `address_2`, `city`, `state`, `postal_code`
- Partner create/edit forms now capture mailing address.
- Partner detail shows mailing address when available.

Contact workflow:

- Added contact delete route:
  - POST-only
  - partner-detail context only
  - no modal/soft-delete/audit system

UI conventions:

- Added Bootstrap Icons in shared base template.
- Harmonized compact list/table actions to icon controls:
  - pencil (`bi-pencil`) for edit
  - trashcan (`bi-trash`) for contact delete
- Kept larger header actions readable with icon + text labels.

Importer updates (`scripts/import_vendors.py`):

- Maps spreadsheet address fields into Partner mailing-address fields:
  - `Address 1`, `Address 2`, `City`, `State`, `Zip`
- Conservatively backfills missing partner address/email/phone when duplicate partner rows appear.
- Import scope remains Partner + Contact only.

## Phase 0.5 Tooling Added

### Directory structure

- `data/original/` for manually copied source spreadsheets (not committed)
- `data/analysis/` for generated markdown profiling reports (not committed)
- `data/imports/` reserved for future import staging artifacts (not committed)
- `.gitkeep` files included to preserve folder structure in git

### Script

- `scripts/analyze_spreadsheet.py`
- `scripts/import_vendors.py` (temporary bootstrap importer)

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

## Temporary Bootstrap Data Tooling

Purpose:

- Seed realistic demo/testing data into the local development database.
- Keep implementation narrow and operationally transparent.

Importer behavior (`scripts/import_vendors.py`):

- Reads `data/original/vendors.xlsx` by default (or explicit path).
- Imports `Partner` and `Contact` records only.
- Supports sparse rows and skips obviously blank contacts.
- Logs summary counts and skipped-contact reasons.
- Supports `--dry-run` (parse/plan only, no writes).
- Supports optional `--reset`:
  - deletes `Contact` rows first
  - deletes `Partner` rows second
  - preserves Campaigns, Users, and Persons

Intentional limits:

- Not a generalized import/reconciliation platform.
- No upload UI, import history, fuzzy matching, or ETL abstraction.
- No Campaign/Solicitation/bootstrap analytics import.

## People Seed Preservation Utility

Purpose:

- Preserve manually maintained committee `Person` records across local database rebuilds.

Scripts:

- `scripts/export_people.py`
- `scripts/import_people.py`

Seed path:

- `data/seeds/people.json`

Usage:

- Export:
  - `uv run python scripts/export_people.py`
- Import:
  - `uv run python scripts/import_people.py`

Scope and limits:

- Person-only utility (no User export/import).
- No backup framework, migration framework, or generalized ETL behavior.

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
3. Keep Solicitation enhancements incremental (correspondence dates and automation remain deferred).
4. Preserve local Windows deployment compatibility and Linux portability when adding runtime behavior.
