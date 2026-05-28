# Solicitation v1 (Architectural Specification)

## Status and Scope

This document is the final architectural/business-process checkpoint before Solicitation implementation in ScholarBridge.

Scope of this document:

- Define Solicitation as a domain entity
- Define business meaning, relationships, and operational semantics
- Define v1 field candidates and rationale
- Identify focused open questions to resolve before implementation

Out of scope:

- SQLAlchemy model code
- Flask routes or handlers
- HTML templates
- migrations
- any implementation code

## Purpose

A **Solicitation** represents:

**A Partner participating in a Campaign.**

Solicitation is the central operational entity in ScholarBridge. It resolves the many-to-many relationship between Partner and Campaign while capturing planning, assignment, correspondence, and outcome data needed for annual committee operations and continuity.

## Canonical Relationships

### Partner 1-to-many Solicitation

- One Partner may appear in many campaign years.
- Each Solicitation belongs to exactly one Partner.
- This supports long-term partner history without overloading the Partner record with campaign-specific data.

### Campaign 1-to-many Solicitation

- One Campaign contains many Solicitation records.
- Each Solicitation belongs to exactly one Campaign.
- This provides clear annual boundaries for planning, execution, and reporting.

### Person 1-to-many Solicitation (as Solicitor)

- `solicitor_person_id` references `Person`.
- A Person may own many Solicitation records within or across campaigns.
- This captures real-world committee ownership independently from system login accounts.

### Person 1-to-many Solicitation (as MRPOC)

- `mrpoc_person_id` references `Person`.
- A Person may be MRPOC for many Solicitation records.
- This captures Example Organization internal liaison context for correspondence copying and operational coordination.

### User relationship (indirect only)

- User remains an authentication/account entity.
- Solicitation ownership and operational roles are person-based.
- User linkage is indirect through Person and should not define business ownership semantics.

## v1 Field Candidates and Rationale

### Core relationships

- `partner_id` (required): binds solicitation to the participating Partner.
- `campaign_id` (required): binds solicitation to the campaign year/context.

Rationale: these fields define the core participation record.

### Stewardship roles

- `solicitor_person_id` (required in normal operations): operational owner responsible for outreach and follow-up.
- `mrpoc_person_id` (optional pending business confirmation): Example Organization point of contact for coordination/copying.

Rationale: role clarity supports accountability, handoff continuity, and workload planning.

### Campaign planning

- `tranche` (optional but strongly recommended): solicitation wave indicator within campaign.
- `business_volume` (optional): approximate annual dollar business volume between Partner and Example Organization.
- `amount_requested` (optional): planned ask amount for this campaign/partner context.

Rationale: these fields support planning decisions and wave-based execution.

### Results

- `amount_received` (optional): received amount attributable to this solicitation record.

Rationale: campaign execution needs a single record of outcomes by partner participation instance.

### Correspondence tracking

- `solicitation_sent_at` (optional): when solicitation correspondence was sent.
- `thank_you_sent_at` (optional): when acknowledgment/thank-you was sent.
- `tax_letter_sent_at` (optional): when tax letter was sent.

Rationale: committee operations need clear timestamp visibility for outbound communications.

### Workflow

- `status` (required): operational state indicator.
- `notes` (optional): free-form context, exceptions, and handoff details.

Rationale: supports day-to-day coordination without rigid process automation.

### Audit

- `created_at` (required)
- `updated_at` (required)

Rationale: minimum temporal traceability for continuity and review.

## Tranche Behavior (v1)

Facts and intent:

- Tranche is campaign-specific.
- Tranche represents solicitation waves.
- Current planning intent is three waves:
  - Tranche 1
  - Tranche 2
  - Tranche 3
- Earlier tranches generally represent higher-priority or higher-yield partners.
- Tranche helps distribute solicitor workload through the campaign timeline.

v1 recommendation:

- Store tranche as integer values `1`, `2`, `3`.
- Present in UI/reporting as `"Tranche 1"`, `"Tranche 2"`, `"Tranche 3"`.
- Treat tranche as planning metadata for prioritization and workload balancing, not as a hard process gate.

## Business Volume Semantics

`business_volume` represents the approximate dollar volume of business conducted between a Partner and Example Organization, supplied by Example Health Services financial staff.

Intended usage:

- planning context for solicitation strategy
- reference signal for determining a reasonable ask amount

Explicit non-usage:

- not a pay-to-play signal
- not a contractual/procurement control field

Why this belongs on Solicitation (not Partner):

- business volume can vary by campaign year
- business volume is used in campaign-specific ask planning
- preserving yearly values supports historical interpretation and auditability of ask strategy over time

## Solicitor Semantics

Solicitor is a role played by a **Person**, not a User account type.

Key semantics:

- A Solicitor may or may not have a User account.
- A User may or may not be a Solicitor.
- Solicitor assignment should persist as institutional identity even if login accounts change.

Therefore `solicitor_person_id` references `Person`.

## MRPOC Semantics

MRPOC = **Example Organization Point of Contact**.

Known v1 intent:

- typically (possibly always) a Example Organization employee
- included for correspondence-copy and coordination context
- represented as `mrpoc_person_id` referencing `Person`

Assumptions requiring confirmation before implementation:

- whether MRPOC is always required, or optional
- whether MRPOC can be outside Example Organization in exception cases
- whether one default MRPOC should auto-populate for specific partner categories

## Status Model (v1)

Recommended status vocabulary:

- `not_contacted`
- `contacted`
- `responded`
- `donated`
- `declined`
- `closed`

Interpretation:

- status provides operational visibility and reporting consistency
- status is not intended to enforce rigid workflow sequencing in v1
- committee discretion remains primary for real-world exceptions

## Uniqueness Assumption

Working assumption:

- One Partner should normally have at most one Solicitation per Campaign.

Rationale:

- reflects the business meaning of “partner participating in campaign”
- avoids duplicate operational ownership and conflicting status/outcome records
- keeps reporting totals and campaign counts interpretable

Implications:

- duplicates should be treated as data quality exceptions
- if edge cases require multiple asks for one partner in one campaign, that should be an explicit post-v1 policy decision, not accidental v1 behavior

## Reporting Implications

Solicitation is the anchor for future reporting, including:

- campaign summaries (counts, status distribution, requested vs received)
- donation totals by campaign and across years
- tranche tracking (pipeline and wave performance)
- solicitor workload/performance views
- partner history across annual campaigns
- annual continuity and handoff reporting

## Focused Open Questions Before Implementation

1. Should `solicitor_person_id` be strictly required at record creation, or allowed temporarily null during intake?
2. Should `mrpoc_person_id` be required, optional, or conditionally required by partner category/workflow stage?
3. Should `business_volume` represent a point-in-time value for the campaign year only, or allow periodic in-year revision tracking in notes?
4. What is the exact semantic distinction between `declined` and `closed` for committee reporting?
5. Should `tax_letter_sent_at` remain a distinct field in v1, or be deferred if operationally redundant with thank-you workflows?

## v1 Design Summary

Solicitation v1 is defined as the campaign-scoped participation record linking Partner and Campaign, with person-based ownership and correspondence/outcome tracking. It is intentionally lightweight, operationally transparent, and continuity-oriented, with status used for visibility rather than strict workflow enforcement.
