# Domain Model (Conceptual)

This document defines likely domain entities and relationships in business terms only. It intentionally avoids ORM and schema implementation details.

## Entity Concepts

### Partner

A donor-aligned institution or group (for example, a business, foundation, parish group, or civic partner) that may provide recurring or one-time support.

### Contact

A person associated with a partner (or potentially individual giving) who is involved in communication, decision-making, or administrative coordination.

### Campaign

A named annual or seasonal solicitation period used to group outreach planning, activity tracking, and outcomes for reporting consistency.

### Solicitation

A campaign-specific solicitation management record representing a partner participating in a campaign. A solicitation may include amount requested, amount donated, solicitation management notes, acknowledgment tracking, and assigned committee ownership.

### Person

A real-world committee participant record used for assignment ownership, historical continuity, and handoff across campaign years.

### User

A committee member or staff participant who accesses ScholarBridge to manage records and solicitation management workflow.

## Relationship Narrative

- A partner may be associated with multiple contacts over time.
- A contact may change role, ownership, or activity status across years.
- Each campaign contains many solicitations.
- A solicitation links solicitation management activity to a specific campaign and partner context.
- A person may own many solicitations across campaigns.
- A user creates and updates records to support continuity and accountability.

Current intended cardinality:

- Partner 1-to-many Contact
- Partner 1-to-many Solicitation
- Campaign 1-to-many Solicitation
- Person 1-to-many Solicitation
- User 1-to-many Solicitation

The detailed relationship cardinality and lifecycle rules should be finalized only after workflow decisions and spreadsheet mapping are validated.
