# Schema v1 (Stable Conceptual Specification)

## Status and Scope

This document defines the first stable conceptual schema for ScholarBridge. It is architecture guidance for implementation planning and review.

ScholarBridge remains a lightweight donor stewardship CRM centered on annual organization-based campaigns. The design prioritizes operational simplicity, stewardship continuity, and historical reporting for non-technical committee users.

This specification intentionally excludes implementation artifacts:

- No SQL DDL
- No ORM model code
- No migration scripts
- No application route or UI definitions

## v1 Design Constraints

- Organization-centric stewardship model
- No standalone individual donor model in v1
- Exactly one campaign per `campaign_year` (conceptually unique year)
- One annual active campaign context at a time, with historical campaign visibility
- Solicitation as the primary operational and reporting entity
- Conservative scope; avoid automation-heavy or accounting-style behavior

## Conceptual Entities

### Organization

Represents a donor/vendor/business organization that may participate in campaigns across multiple years.

Conceptual responsibilities:

- Provide institutional identity for stewardship history
- Act as parent record for contacts
- Act as parent record for campaign solicitations

Tentative fields:

- id (required)
- organization_name (required)
- display_name (optional)
- organization_type (optional)
- address_line_1 (optional)
- address_line_2 (optional)
- city (optional)
- state_or_region (optional)
- postal_code (optional)
- country (optional)
- phone_main (optional)
- email_main (optional)
- website (optional)
- organization_notes (optional)
- is_active (required)
- created_at (required)
- updated_at (required)

`organization_type` usage note (v1):

- This existing field serves as the organization type/category field.
- It remains optional and nullable.
- UI data entry should use a controlled single-select vocabulary:
  - Construction
  - Environmental Services
  - Facilities Maintenance
  - Financial Services
  - Food Services
  - Healthcare Services
  - Insurance
  - Landscaping
  - Legal Services
  - Management Services
  - Other
  - Renovation
  - Resident Services
  - Sustainability
  - Technology Services
  - Utilities

### Contact

Represents a human contact associated with exactly one Organization.

Scope note:

- ScholarBridge v1 does not support standalone individual donors.
- Every Contact must belong to one and only one Organization.

Conceptual responsibilities:

- Capture who committee members communicate with at an organization
- Preserve role and communication context over time

Tentative fields:

- id (required)
- organization_id (required)
- first_name (required)
- last_name (required)
- preferred_name (optional)
- title_or_role (optional)
- email (optional)
- phone (optional)
- address_line_1 (optional)
- address_line_2 (optional)
- city (optional)
- state_or_region (optional)
- postal_code (optional)
- preferred_contact_method (optional)
- is_primary_for_organization (required)
- contact_notes (optional)
- is_active (required)
- created_at (required)
- updated_at (required)

### Campaign

Represents an annual solicitation campaign.

Conceptual responsibilities:

- Define annual stewardship/reporting boundary
- Group related solicitations for operational tracking and historical comparison

Status vocabulary (v1):

- `planned`
- `active`
- `closed`
- `archived`

Conceptual constraints:

- `campaign_year` is conceptually unique (exactly one campaign per year).
- One active campaign at a time is the normal operating model.
- `campaign_name` should follow a consistent reporting/export format: `"{campaign_year} Scholarship Campaign"` (for example, `"2026 Scholarship Campaign"`).

Tentative fields:

- id (required)
- campaign_name (required)
- campaign_year (required)
- start_date (optional)
- end_date (optional)
- status (required)
- target_amount (optional)
- planning_notes (optional)
- is_active (required)
- created_at (required)
- updated_at (required)

### Person

Represents a real human in institutional/operational terms. This aligns philosophically with Clerk's Person concept.

Conceptual responsibilities:

- Identify who owns stewardship work in real-world committee operations
- Support continuity when login/account details change

Tentative fields:

- id (required)
- first_name (required)
- last_name (required)
- preferred_name (optional)
- email (optional)
- phone (optional)
- committee_role (optional)
- is_active (required)
- person_notes (optional)
- created_at (required)
- updated_at (required)

### User

Represents a technical authentication/account entity used for system access.

Conceptual responsibilities:

- Support authentication and technical account lifecycle
- Optionally map technical accounts to real people for operational context

Authentication assumption (v1):

- Conventional local authentication only.

Tentative fields:

- id (required)
- username (required)
- email (required, conceptually unique)
- password_hash (required)
- person_id (optional, unique when present)
- is_active (required)
- last_login_at (optional)
- created_at (required)
- updated_at (required)

### Solicitation

Represents an Organization participating in a Campaign. This is the central stewardship entity in v1.

Conceptual responsibilities:

- Capture organization-level campaign participation
- Record stewardship progress and outcomes
- Preserve ownership accountability through assigned person

Canonical ownership rule:

- `Solicitation.assigned_person_id` is the canonical stewardship ownership relationship.

Status vocabulary (v1):

- `not_contacted`
- `contacted`
- `responded`
- `donated`
- `declined`
- `closed`

Tentative fields:

- id (required)
- campaign_id (required)
- organization_id (required)
- assigned_person_id (required)
- primary_contact_id (optional)
- solicitation_status (required)
- amount_requested (optional)
- amount_received (optional)
- amount_received_date (optional)
- outreach_last_date (optional)
- outreach_next_date (optional)
- thank_you_sent_at (optional)
- stewardship_notes (optional)
- created_at (required)
- updated_at (required)

## Required Conceptual Relationships

- Organization 1-to-many Contact
- Organization 1-to-many Solicitation
- Campaign 1-to-many Solicitation
- Person 1-to-many Solicitation
- User optional 1-to-1 Person

Relationship rationale:

- Contact is organization-scoped to preserve a simple organization-first model.
- Solicitation links campaign and organization to represent annual participation.
- Assigned person is required to ensure stewardship accountability and handoff continuity.
- User and Person are intentionally separated so technical account management does not define institutional identity.

## Lifecycle Considerations

- Organizations and contacts are generally long-lived; prefer inactive status over deletion.
- Campaigns are annual with exactly one campaign per year.
- Campaign operations normally run with one active campaign at a time.
- Solicitations are campaign-scoped records and should remain immutable as historical evidence once campaigns close, except for correction workflows.
- Solicitation closure tracking in v1 uses `solicitation_status` together with `updated_at`; no dedicated `closed_at` field is included.
- Persons may remain in records after committee transitions for stewardship continuity.
- Users may be deactivated independently of Person records.

## Required vs Optional Data Reasoning

- Required identifiers and foreign keys preserve baseline relational integrity and reporting usefulness.
- `Campaign.campaign_year` is conceptually unique to preserve annual reporting clarity.
- Amount fields remain optional to support records that are created before financial outcomes are known.
- `User.email` is required and conceptually unique in v1.
- Dates tied to outreach, donation receipt, and thank-you completion are optional because these events may not occur for every solicitation.
- `primary_contact_id` remains optional in v1 to avoid blocking useful stewardship work when contact data is sparse or incomplete.
- Contact communication data (for example email and phone) remains optional in v1 to support organization-only solicitation records where contact details are incomplete.

## Operational Rationale

- Non-technical committee workflows benefit from clear ownership (`assigned_person_id`) and lightweight status tracking.
- Campaign-scoped solicitations provide predictable annual reporting without requiring advanced fundraising abstractions.
- Person/User separation supports stable institutional handoff even if account credentials or local login policies change.
- Timestamp-based thank-you tracking keeps acknowledgment workflows simple while preserving accountability.
- In v1, the thank-you letter is assumed to also serve as donor acknowledgment/tax letter tracking through `thank_you_sent_at`; no separate `tax_letter_sent_at` field is included.

## Historical Reporting Goals

v1 should support:

- Campaign-by-campaign comparison of organization participation
- Requested vs received amount rollups by campaign
- Acknowledgment completion visibility
- Stewardship workload visibility by assigned person
- Preservation of historical context across leadership transitions

## Annual Campaign Workflow Assumptions

- Exactly one campaign exists per campaign year.
- One active campaign at a time is the normal operating model.
- Organizations may recur across campaigns.
- Each campaign creates a new solicitation context for each participating organization.
- Stewardship assignment is person-based and should be explicit early in the campaign cycle.

## Stewardship Continuity and Institutional Handoff

- Preserve closed-campaign solicitations for future reference and onboarding.
- Keep ownership and notes attached to solicitations to reduce reliance on informal memory.
- Maintain person records beyond active service periods to preserve historical accountability context.

## Deferred/Future Possibilities

Intentionally deferred from v1:

- Pledge lifecycle tracking and pledge-to-payment reconciliation
- Multi-stage fundraising pipeline workflows
- Polymorphic or multi-entity contact ownership
- Automation-heavy reminders/orchestration rules
- Accounting-system integration behavior
- Separate tax-letter tracking fields/workflows
- Expanded authentication/provider abstractions
- Complex role/permission hierarchies beyond current operational needs
