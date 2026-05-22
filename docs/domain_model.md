# Domain Model (Conceptual)

This document defines likely domain entities and relationships in business terms only. It intentionally avoids ORM and schema implementation details.

## Entity Concepts

### Organization

A donor-aligned institution or group (for example, a business, foundation, parish group, or civic organization) that may provide recurring or one-time support.

### Contact

A person associated with an organization (or potentially individual giving) who is involved in communication, decision-making, or administrative coordination.

### Campaign

A named annual or seasonal solicitation period used to group outreach planning, activity tracking, and outcomes for reporting consistency.

### Solicitation

A campaign-specific stewardship record representing an organization participating in a campaign. A solicitation may include amount requested, amount donated, stewardship notes, acknowledgment tracking, and assigned committee ownership.

### User

A committee member or staff participant who accesses ScholarBridge to manage records and stewardship workflow.

## Relationship Narrative

- An organization may be associated with multiple contacts over time.
- A contact may change role, ownership, or activity status across years.
- Each campaign contains many solicitations.
- A solicitation links stewardship activity to a specific campaign and organization context.
- A user creates and updates records to support continuity and accountability.

Current intended cardinality:

- Organization 1-to-many Contact
- Organization 1-to-many Solicitation
- Campaign 1-to-many Solicitation
- User 1-to-many Solicitation

The detailed relationship cardinality and lifecycle rules should be finalized only after workflow decisions and spreadsheet mapping are validated.
