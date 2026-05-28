# Roadmap

This roadmap is phased to reduce risk, preserve committee continuity, and deliver usable improvements early.

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

## Phase 3: Letter Generation

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

- Harden local Apache-hosted Flask deployment on Windows 11
- Add operational procedures for backup, restore, and updates
- Prepare Linux-compatible deployment path
- Introduce multi-user handling, roles, and operational governance controls
