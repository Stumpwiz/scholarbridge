# Schema Draft (Provisional)

This draft is intentionally provisional and subject to change after stakeholder review and spreadsheet-mapping validation.

No SQL syntax or ORM code is included here. This is a field-planning aid only.

## Organization (tentative fields)

- organization_name
- display_name
- organization_type
- primary_address_line_1
- primary_address_line_2
- city
- state_or_region
- postal_code
- country
- phone_main
- email_main
- website
- stewardship_notes
- is_active
- created_at
- updated_at

## Contact (tentative fields)

- contact_first_name
- contact_last_name
- preferred_name
- title_or_role
- email
- phone
- mailing_address_line_1
- mailing_address_line_2
- city
- state_or_region
- postal_code
- preferred_contact_method
- relationship_notes
- is_primary_for_organization
- is_active
- created_at
- updated_at

## Campaign (tentative fields)

- campaign_name
- campaign_year
- start_date
- end_date
- target_amount
- status
- planning_notes
- created_at
- updated_at

## Solicitation (tentative fields)

- solicitation_code
- campaign_reference
- organization_reference
- contact_reference
- assigned_user_reference
- solicitation_status
- last_outreach_date
- next_follow_up_date
- requested_amount
- pledged_amount
- donated_amount
- donation_received_date
- contribution_type
- acknowledgment_status
- acknowledgment_sent_date
- stewardship_notes
- created_at
- updated_at

## User (tentative fields)

- username
- display_name
- email
- role
- is_active
- last_login_at
- created_at
- updated_at

## Cross-Cutting Considerations

- Track historical continuity across campaigns without overwriting prior-year outcomes.
- Preserve source-traceability for imported spreadsheet data.
- Keep optional fields explicit to avoid accidental data loss during migration.

## Relationship Intent (Conceptual)

- Organization 1-to-many Contact
- Organization 1-to-many Solicitation
- Campaign 1-to-many Solicitation
- User 1-to-many Solicitation
