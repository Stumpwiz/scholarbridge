from __future__ import annotations

from typing import Any

PARTNER_TYPE_NEEDS_REVIEW = "Needs Review"


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _partner_contact_for_completeness(partner: Any) -> Any | None:
    contacts = getattr(partner, "contacts", None)
    if not contacts:
        return None

    primary_contact = next((contact for contact in contacts if getattr(contact, "is_primary", False)), None)
    return primary_contact or contacts[0]


def partner_is_incomplete(partner: Any) -> bool:
    if partner is None:
        return True

    partner_type = getattr(partner, "partner_type", None)
    if _is_missing(partner_type):
        return True
    if isinstance(partner_type, str) and partner_type.strip() == PARTNER_TYPE_NEEDS_REVIEW:
        return True

    contact = _partner_contact_for_completeness(partner)
    if contact is None:
        return False

    return any(
        _is_missing(getattr(contact, field_name, None))
        for field_name in ("first_name", "last_name", "title")
    )


def _solicitation_has_solicitor(solicitation: Any) -> bool:
    return (
        getattr(solicitation, "solicitor_person_id", None) is not None
        or getattr(solicitation, "solicitor", None) is not None
    )


def _person_has_required_letter_fields(person: Any) -> bool:
    if person is None:
        return False

    phone = (
        getattr(person, "phone", None)
        or getattr(person, "mobile_phone", None)
        or getattr(person, "other_phone", None)
    )
    return not any(
        _is_missing(value)
        for value in (
            getattr(person, "first_name", None),
            getattr(person, "last_name", None),
            getattr(person, "email", None),
            phone,
        )
    )


def solicitation_is_incomplete(solicitation: Any) -> bool:
    if solicitation is None:
        return True

    if partner_is_incomplete(getattr(solicitation, "partner", None)):
        return True

    if not _solicitation_has_solicitor(solicitation):
        return True

    if not _person_has_required_letter_fields(getattr(solicitation, "solicitor", None)):
        return True

    if not _person_has_required_letter_fields(getattr(solicitation, "mrpoc", None)):
        return True

    return _is_missing(getattr(solicitation, "business_volume", None))


def solicitation_is_ready(solicitation: Any) -> bool:
    """Operational readiness for statistics: partner ready + business_volume + amount_requested."""
    if solicitation is None:
        return False

    if partner_is_incomplete(getattr(solicitation, "partner", None)):
        return False

    if _is_missing(getattr(solicitation, "business_volume", None)):
        return False

    return not _is_missing(getattr(solicitation, "amount_requested", None))


def solicitation_is_letter_ready(solicitation: Any) -> bool:
    if solicitation_is_incomplete(solicitation):
        return False

    return not _is_missing(getattr(solicitation, "amount_requested", None))
