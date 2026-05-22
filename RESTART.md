# RESTART NOTES: ScholarBridge

This file provides resume context for future assistants and maintainers.

Current stage: **Phase 0.75 (stabilized conceptual schema)**.

The project remains documentation-first and discovery-focused. There is still no Flask app, no ORM models, no auth layer, and no UI implementation.

## Project Snapshot

- Name: ScholarBridge
- Domain: Donor/patron CRM for the Example Scholarship Committee
- Goal: Institutional continuity, stewardship quality, and historical traceability
- Current operational baseline: legacy spreadsheet process

## Core Intent

ScholarBridge should evolve spreadsheet-era operations into a maintainable system without dismissing existing committee practices. Current work is focused on understanding legacy data structure before any schema or application code is finalized.

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

See `requirements.txt`:

- pandas
- openpyxl

## Guidance for Next Assistant

1. Run spreadsheet analysis and review markdown report before proposing schema changes.
2. Treat heuristics as directional, not authoritative.
3. Treat `docs/schema_v1.md` as the implementation baseline unless committee policy changes.
4. Continue to defer Flask/ORM/UI implementation until the committee confirms readiness to begin build phase.
