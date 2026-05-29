# Authentication and Role Model v1

## Status and Scope

This document defines v1 authentication role expectations and user access behavior for ScholarBridge. It is operational guidance for committee review prior to implementation.

Out of scope:

- SQLAlchemy models
- Flask routes
- templates
- migrations
- implementation code

## Role Model (v1)

ScholarBridge has two v1 system roles:

- Editor
- Reader

## Editor Permissions

Editors may:

- create records
- edit records
- update records
- delete records
- assign Partners
- assign Solicitors
- manage Campaigns
- manage Contacts

## Reader Permissions

Readers may:

- browse records
- search records
- view details
- run reports (future capability)

Readers may not:

- create
- update
- delete
- assign

## UI Expectations for Reader Mode

- Reader users should still see operational data needed for review.
- Create/Edit/Delete/Assign controls should be hidden or clearly disabled/grayed out.
- Reader mode should be visually obvious but not disruptive to normal viewing workflows.
- Permission limits should be consistently communicated by interface state, not error-driven discovery.

## Person and User Concepts

### Person

- Represents a human identity in committee operations.
- Supports stewardship, assignment, and continuity semantics.

### User

- Represents a login identity for system access.
- A User may be linked to a Person.

## Current v1 Assumptions

- Solicitor must be an Editor.
- Not all Persons are Users.
- Not all Users are Solicitors.
- Not all Solicitors require ongoing system use.

Operational implication: solicitation ownership semantics should remain person-aware even when login/account status changes over time.

## Avatar Expectations

- Users may upload avatars.
- A default avatar should exist.
- Avatars are convenience features, not core workflow features.

## Remaining Open Questions

1. Should role changes require one Editor, two Editors, or a future Admin approval workflow?
2. Should Reader access include export/download in v1 or only on-screen read/report access?
3. What is the committee policy for inactive Users linked to active Person records?
4. Is a future Admin role required, or can Editor/Reader remain sufficient through v1 and early v2?

## Implementation Implications (Next Phase)

- Authentication development should enforce role-based permissions server-side, not only in UI controls.
- UI development should implement clear Reader-mode states for action controls across campaigns, partners, contacts, and solicitations.
- Solicitation assignment logic should validate that selected Solicitor accounts have Editor role.
- Identity design should preserve distinction between Person records (operational identity) and User accounts (access identity) to support continuity.
