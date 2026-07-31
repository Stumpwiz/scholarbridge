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
    return bool(_partner_readiness_issues(partner))


def _partner_readiness_issues(partner: Any) -> list[str]:
    if partner is None:
        return ["Partner record is missing."]

    issues = []
    partner_type = getattr(partner, "partner_type", None)
    if _is_missing(partner_type):
        issues.append("Partner category is missing.")
    elif isinstance(partner_type, str) and partner_type.strip() == PARTNER_TYPE_NEEDS_REVIEW:
        issues.append("Partner category is still marked as 'Needs Review'.")

    # An absent contact is intentionally allowed. Once a contact exists, the
    # selected primary (or first) contact must have the letter name fields.
    contact = _partner_contact_for_completeness(partner)
    if contact is not None:
        if _is_missing(getattr(contact, "title", None)):
            issues.append("Primary contact title is missing.")
        if _is_missing(getattr(contact, "first_name", None)):
            issues.append("Primary contact first name is missing.")
        if _is_missing(getattr(contact, "last_name", None)):
            issues.append("Primary contact last name is missing.")

    return issues


def _solicitation_has_solicitor(solicitation: Any) -> bool:
    return (
        getattr(solicitation, "solicitor_person_id", None) is not None
        or getattr(solicitation, "solicitor", None) is not None
    )


def _person_has_required_letter_fields(person: Any) -> bool:
    return not _person_readiness_issues(person, "Person")


def _person_readiness_issues(person: Any, role_label: str) -> list[str]:
    if person is None:
        return [f"{role_label} is missing."]

    issues = []
    if _is_missing(getattr(person, "first_name", None)):
        issues.append(f"{role_label} first name is missing.")
    if _is_missing(getattr(person, "last_name", None)):
        issues.append(f"{role_label} last name is missing.")
    if _is_missing(getattr(person, "email", None)):
        issues.append(f"{role_label} email is missing.")

    phone = (
        getattr(person, "phone", None)
        or getattr(person, "mobile_phone", None)
        or getattr(person, "other_phone", None)
    )
    if _is_missing(phone):
        issues.append(f"{role_label} phone is missing.")
    return issues


def _solicitation_profile_issues(solicitation: Any) -> list[str]:
    if solicitation is None:
        return ["Solicitation record is missing."]

    issues = []
    if not _solicitation_has_solicitor(solicitation):
        issues.append("Solicitor is missing.")
    else:
        issues.extend(
            _person_readiness_issues(getattr(solicitation, "solicitor", None), "Solicitor")
        )
    issues.extend(_person_readiness_issues(getattr(solicitation, "mrpoc", None), "MRPOC"))
    return issues


def solicitation_is_incomplete(solicitation: Any) -> bool:
    if solicitation is None:
        return True

    return bool(
        _partner_readiness_issues(getattr(solicitation, "partner", None))
        or _solicitation_profile_issues(solicitation)
    )


def solicitation_readiness_diagnostics(
    solicitation: Any, *, for_letter: bool = False
) -> dict[str, Any]:
    """Return field-specific operational or letter-readiness diagnostics."""
    if solicitation is None:
        partner_issues = ["Partner record is missing."]
        solicitation_issues = ["Solicitation record is missing."]
    else:
        partner_issues = _partner_readiness_issues(getattr(solicitation, "partner", None))
        solicitation_issues = []
        if _is_missing(getattr(solicitation, "amount_requested", None)):
            solicitation_issues.append("Requested amount is missing.")
        if for_letter:
            solicitation_issues.extend(_solicitation_profile_issues(solicitation))

    return {
        "is_ready": not partner_issues and not solicitation_issues,
        "partner_issues": partner_issues,
        "solicitation_issues": solicitation_issues,
    }


def solicitation_is_ready(solicitation: Any) -> bool:
    return solicitation_readiness_diagnostics(solicitation)["is_ready"]


def solicitation_is_letter_ready(solicitation: Any) -> bool:
    return solicitation_readiness_diagnostics(solicitation, for_letter=True)["is_ready"]


def partner_readiness_summary(partner: Any) -> dict:
    """Return a dict with 'is_complete' (bool) and 'missing' (list of str)."""
    missing = _partner_readiness_issues(partner)
    return {"is_complete": len(missing) == 0, "missing": missing}
