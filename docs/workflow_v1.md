# Campaign Workflow v1

## Status and Scope

This document defines the v1 annual campaign lifecycle and stewardship workflow for ScholarBridge. It is a committee operations document, not implementation design.

Out of scope:

- SQLAlchemy models
- Flask routes
- templates
- migrations
- implementation code

## Purpose and Rationale

The campaign workflow should be consistent year to year, simple for committee use, and clear enough to preserve institutional memory across leadership transitions. v1 prioritizes operational clarity over workflow automation.

## Annual Campaign Lifecycle (v1)

1. Editor creates a Campaign for the annual cycle.
2. Campaign is initialized with three implicit tranches:
   - Tranche 1
   - Tranche 2
   - Tranche 3
3. Editors assign Partners to a tranche within that Campaign.
4. Editors assign a Solicitor for each campaign participation record.
5. MRPOC is assigned automatically using campaign-defined category-to-MRPOC mappings.
6. Solicitation activities are managed:
   - solicitation letter
   - follow-up
   - donation tracking
   - acknowledgments
7. Campaign closes.
8. Historical campaign records remain available for continuity and reporting.

## Tranche and Assignment Rules

- Tranches are system-defined and always present in each Campaign.
- Users do not create tranches.
- A Partner may be assigned to only one tranche within a Campaign.
- Partner tranche assignment is intended to be permanent for that Campaign.
- v1 UI should only offer Partners not already assigned in that Campaign to prevent duplicates.

## Role and Ownership Semantics

### Editor Ownership

- Editor is the operational owner of campaign setup and assignment decisions.
- Editors manage Partner assignments and Solicitor assignments.

### Solicitor Assignment

- Solicitor is the accountable owner of solicitation execution for assigned records.
- v1 implementation does not enforce authentication role gates yet (reader/editor enforcement deferred).

### MRPOC Assignment

- MRPOC assignment is automatic in v1.
- MRPOC is determined by Partner category.
- Category-to-MRPOC mappings are established per Campaign.
- Canonical partner categories used for mapping:
  - Food and Beverage
  - Finance
  - Insurance
  - Accounting
  - HR
  - IT
  - Security Services
  - Construction
  - Renovation
  - Grounds
  - Moving
  - Packing
  - Medical Service Providers
  - Personal Service Providers
  - Cleaning Services and Supplies
  - Admin
- Mapping is campaign-specific, so the same category may resolve to different MRPOCs in different years.
- MRPOCs are generally Example Organization employees.
- MRPOC assignments may change between Campaigns.
- Mid-campaign remapping is not a v1 concern.
- Missing category mapping does not block solicitation creation; MRPOC remains blank until manually set.
- Partners with legacy categories are marked `Needs Review` until committee cleanup.

## Stewardship Philosophy

- The system should support respectful, consistent relationship stewardship rather than transactional-only tracking.
- Assignment clarity (Editor, Solicitor, MRPOC) is used to improve accountability and reduce dropped follow-up.
- Historical context should remain visible so outreach reflects prior relationships and outcomes.

## Operational Assumptions

- Annual campaigns are the primary planning and reporting boundary.
- Three tranches are sufficient for v1 workload organization.
- One Partner participation record per Campaign is the working rule in v1.
- Assignment stability inside a campaign improves execution discipline and reporting clarity.
- Committee discretion remains necessary for exceptions not covered by v1 workflow rules.

## Continuity Considerations

- Closed campaigns must remain queryable and readable.
- Prior-year assignments and outcomes should remain visible to support leadership handoff.
- Category-to-MRPOC mapping history should be preserved by campaign year.
- Workflow language and behavior should remain predictable to reduce onboarding burden for new committee members.

## Remaining Open Questions

1. Should authorized exceptions ever allow reassignment of a Partner to a different tranche after active solicitation has started?
2. What is the committee policy for handling merged/split Partner identities within an active campaign?
3. When a Solicitor leaves mid-campaign, should reassignment require a specific approval path or simple Editor action?
4. Which closure criteria are required before campaign status can move to closed?

## Implementation Implications (Next Phase)

- Solicitation development should treat Campaign + Partner pairing as unique within a campaign year.
- Assignment UI should enforce the single-tranche-per-partner rule by filtering out already-assigned Partners.
- Campaign configuration should include category-to-MRPOC mapping setup before active solicitation work begins.
- Auditability should focus on assignment ownership, status progression, and closure readiness at campaign scope.
