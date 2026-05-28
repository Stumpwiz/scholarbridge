# UI Concepts (Pre-Implementation)

## Purpose

This document defines the intended ScholarBridge user experience before implementation work begins. It translates the stabilized conceptual schema and solicitation management model into practical UI responsibilities, navigation concepts, and operational workflows suitable for long-term committee continuity.

ScholarBridge is intentionally a lightweight donor solicitation management CRM for non-technical users. The UI should support reliable day-to-day committee work without introducing enterprise-style complexity.

## Overall UI Philosophy

- Keep workflows simple, readable, and predictable.
- Prioritize low cognitive load over feature density.
- Present solicitation management context clearly so users can make good judgment calls.
- Support print-friendly workflows for meetings, mail preparation, and records.
- Help users complete practical tasks; avoid rigid process enforcement where discretion is needed.
- Favor continuity: interface structure should remain stable across committee transitions.

## Primary Navigation Concepts

Likely top-level sections:

- Dashboard
- Partners
- Campaigns
- Solicitations
- Reports
- Letter Generation
- Administration

These sections map to the v1 model and core operational rhythms: annual campaign planning, partner-based solicitations, solicitation management follow-up, and historical reporting.

## Dashboard

Purpose:

- Provide a concise operational snapshot for the active campaign.

Likely workflow:

- User signs in and immediately reviews current priorities.
- User drills into sections requiring action (solicitations, thank-you letters, partner follow-up).

Key information displayed:

- Current campaign summary (counts, totals, status distribution).
- Recent donations/receipts.
- Outstanding solicitations requiring follow-up.
- Pending thank-you letters (`thank_you_sent_at` not yet set).
- Historical comparison summaries (current year vs prior campaigns).

Likely user actions:

- Open solicitation detail for updates.
- Open partner history before outreach.
- Launch report or letter-generation workflows.

Likely future enhancements:

- Configurable dashboard cards by committee role.
- Saved personal views of priority work.

## Partners

Purpose:

- Maintain institutional records for donor/vendor/business partners and their long-term solicitation management context.

Likely workflow:

- Search for a partner.
- Review partner profile, contacts, and historical solicitations.
- Update partner and contact records as solicitation management context changes.

Key information displayed:

- Searchable partner list with basic status and category signals.
- Partner detail page with core profile data.
- Related contacts (partner-bound only in v1).
- Solicitation Management history and notes.
- Historical solicitations across campaigns.

Likely user actions:

- Add/edit partner records.
- Add/edit partner contacts.
- Navigate from partner to solicitation records.

v1 category entry pattern:

- Use the existing partner type/category field with a controlled dropdown list.
- Keep category optional so solicitation management records remain usable when information is incomplete.
- Include an `Other` option for non-standard cases while avoiding taxonomy complexity.

Likely future enhancements:

- Better partner categorization and filtering.
- Optional timeline-style solicitation management history view.

## Campaigns

Purpose:

- Manage annual campaign context and preserve year-over-year continuity.

Likely workflow:

- Create or open the campaign for a specific `campaign_year`.
- Monitor progress and totals throughout the year.
- Close campaign while preserving reportability.

Key information displayed:

- Campaign list with one record per year.
- Active campaign indicator (normal model: one active at a time).
- Campaign summary totals (requested, received, completion indicators).
- Status (`planned`, `active`, `closed`, `archived`).

Likely user actions:

- Create/open campaign.
- Update campaign status.
- Review campaign-level summaries and navigate to associated solicitations.

Likely future enhancements:

- Campaign setup checklist for annual turnover.
- Archive-focused views for older campaigns.

## Solicitations

Purpose:

- Operate the core solicitation management record: a partner participating in a campaign.

Likely workflow:

- Create solicitation for partner within active campaign.
- Assign solicitation management ownership (`assigned_person_id`).
- Track outreach progress, requested/received amounts, and acknowledgment completion.

Key information displayed:

- Solicitation list filtered by campaign, status, owner, and follow-up priority.
- Solicitation Management ownership (person-based).
- Status tracking (`not_contacted`, `contacted`, `responded`, `donated`, `declined`, `closed`).
- Requested vs received amounts.
- Notes/history and next follow-up context.
- Acknowledgment tracking through `thank_you_sent_at`.

Likely user actions:

- Create/edit solicitation.
- Reassign solicitation management owner.
- Update status, amounts, notes, and thank-you completion timestamp.
- Open linked partner context and past campaign history.

Likely future enhancements:

- Bulk status updates for end-of-cycle cleanup.
- Solicitation Management workload balancing views by assigned person.

## Reports

Purpose:

- Provide consistent historical and operational reporting for committee planning and handoff.

Likely workflow:

- Select campaign and report type.
- Review on screen and print/export for meetings.
- Use findings to guide follow-up and annual planning.

Key information displayed:

- Donor history reports by partner.
- Yearly totals.
- Partner category summaries.
- Campaign progress summaries.
- Solicitation Management summaries by assigned person.

Likely user actions:

- Run report by year/campaign.
- Filter/sort for committee review.
- Print or export report artifacts.

Likely future enhancements:

- Saved report presets.
- Side-by-side multi-year comparisons.

## Letter Generation

Purpose:

- Produce practical correspondence outputs tied to solicitation and acknowledgment workflows.

Likely workflow:

- Select campaign/solicitations.
- Generate solicitation letters and thank-you letters.
- Print or batch-export PDFs for mailing and records.

Key information displayed:

- Eligible solicitation records for letter generation.
- Output type (solicitation vs thank-you).
- Generation status and timestamp context.

Likely user actions:

- Generate individual or batch letters.
- Produce printable PDF output.
- Mark correspondence events in solicitation management records when sent.

Likely future enhancements:

- Template version tracking.
- Basic quality checks before batch generation.

## Administration

Purpose:

- Support lightweight operational continuity without enterprise overhead.

Likely workflow:

- Manage user access.
- Run backup/export routines.
- Perform basic data-maintenance checks.

Key information displayed:

- User account list and active/inactive state.
- Backup/export history indicators.
- Basic operational health/maintenance notes.

Likely user actions:

- Add/deactivate user accounts.
- Trigger or verify exports/backups.
- Maintain simple operational settings.

Likely future enhancements:

- Guided admin checklist for committee transitions.
- Simple audit-oriented admin summaries.

## Accessibility and Readability Considerations

- Use clear labels and plain language over technical terms.
- Favor high contrast, readable typography, and predictable page structure.
- Keep forms short and sectioned to reduce fatigue.
- Avoid dense dashboard clutter and unnecessary visual complexity.
- Ensure printable pages remain legible with clean hierarchy.
- Support older users through consistent navigation placement and minimal mode switching.

## Workflow Simplicity and Solicitor Discretion

- Preserve flexibility for real-world committee judgment.
- Avoid forcing rigid sequences when outreach reality is variable.
- Allow partial records so solicitation management can continue even with sparse contact data.
- Keep required fields focused on operational essentials.
- Emphasize clarity of ownership, status, and historical context over administrative overhead.

## Avoiding Enterprise CRM Behavior

ScholarBridge v1 should not mimic enterprise fundraising platforms. It should avoid:

- Overly complex pipeline/stage mechanics.
- Heavy automation and rule orchestration.
- Deep permissions complexity beyond committee needs.
- Accounting-system assumptions.
- Process rigidity that discourages practical solicitation management work.

## Implementation Guidance

- Bootstrap is likely suitable for consistent, maintainable, low-complexity interface construction.
- Server-rendered HTML aligns with predictable workflows and long-term maintainability.
- JavaScript should remain minimal and targeted to usability improvements.
- Form workflows should be conservative, explicit, and resilient to partial data entry.
- Reporting and letter generation should remain print-oriented and operationally practical.
- UI decisions should continue to track `schema_v1` priorities: continuity, solicitation management clarity, and institutional handoff readiness.
