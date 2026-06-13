# Roadmap

This roadmap is phased to reduce risk, preserve committee continuity, and deliver usable improvements early.

## Current Platform Status (as of 2026-06-12)

- PostgreSQL is the primary development/runtime database.
- Legacy SQLite data migration to PostgreSQL has been completed and verified.
- GitHub Actions CI is active and runs migrations/tests against PostgreSQL.
- AWS pilot deployment is live at `https://scholarbridge.example.org`.
- AWS pilot runtime: EC2 `t4g.small` (ARM64), Ubuntu 24.04 LTS, local PostgreSQL, Gunicorn, Nginx, systemd.
- HTTPS is enabled/validated with automatic certificate renewal.
- Nightly PostgreSQL backups are configured with 30-day retention.
- Next major functional decision: committee-approved correspondence generation implementation.

## Phase 0: Discovery and Modeling

- Confirm committee terminology and solicitation management definitions
- Document current spreadsheet structure and annual process variants
- Finalize conceptual domain model and provisional schema priorities
- Identify minimum viable workflows for first operational release

## Phase 1: Spreadsheet Import

- Define import mapping from legacy spreadsheets to structured records
- Build repeatable import validation rules and error reporting
- Test import with representative historical samples
- Establish data quality review and correction workflow

## Phase 2: Basic CRUD UI

- Implement core record management for partners and contacts
- Implement campaign and solicitation creation/update flows
- Add practical search/filter capabilities for committee operations
- Support low-friction data edits during active campaign management

## Phase 3: Committee-Approved Correspondence Generation

- Finalize committee-approved correspondence requirements and template governance
- Standardize acknowledgment content inputs and templates
- Add printable/exportable correspondence generation flow
- Prepare for XeLaTeX-based PDF output integration
- Ensure acknowledgment status tracking is tied to solicitation lifecycle

## Phase 4: Historical Reporting

- Provide year-over-year campaign summaries
- Support solicitation management activity and response trend analysis
- Add export pathways suitable for committee review meetings
- Validate report consistency against known historical spreadsheet totals

## Phase 5: Deployment and Multi-User Operation

- [Completed] Deploy ScholarBridge AWS pilot environment and validate core workflows.
- [Completed] Add operational procedures for backup, restore, and rollback (`docs/deployment/aws-pilot.md`).
- [In Progress] Introduce multi-user handling, roles, and operational governance controls.
