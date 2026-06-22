from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Contact, Partner, Solicitation
from app.services.docx_template_service import DocxTemplateError, DocxTemplateService
from app.services.formatters import clean, month_year, normalize_phone
from app.services.letters import get_letter_template


class SolicitationLetterError(RuntimeError):
    """Raised when solicitation letter generation fails."""


def build_solicitation_letter_context_for_solicitation(solicitation_id: int) -> dict:
    solicitation = db.session.scalar(
        select(Solicitation)
        .options(
            selectinload(Solicitation.partner).selectinload(Partner.contacts),
            selectinload(Solicitation.solicitor),
            selectinload(Solicitation.mrpoc),
            selectinload(Solicitation.campaign),
        )
        .where(Solicitation.id == solicitation_id)
    )
    if solicitation is None:
        raise SolicitationLetterError("Solicitation not found.")
    if solicitation.partner is None:
        raise SolicitationLetterError("Solicitation partner not found.")

    partner = solicitation.partner
    contact = _pick_contact(partner.contacts)
    return _build_solicitation_letter_context(partner, contact, solicitation)


def _build_solicitation_letter_context(
    partner: Partner,
    contact: Contact | None,
    solicitation: Solicitation | None,
) -> dict:

    solicitor = solicitation.solicitor if solicitation is not None else None
    mrpoc = solicitation.mrpoc if solicitation is not None else None
    amount_requested = solicitation.amount_requested if solicitation is not None else None

    formatted_date = month_year()

    salutation = clean(contact.title if contact else None)
    contact_first_name = clean(contact.first_name if contact else None)
    contact_last_name = clean(contact.last_name if contact else None)
    contact_display_name = " ".join(
        part for part in (contact_first_name, contact_last_name) if part
    )
    dear_salutation = salutation or "Sir or Madam"
    dear_last_name = contact_last_name or ""
    dear_line = " ".join(part for part in (dear_salutation, dear_last_name) if part).strip()

    city = clean(partner.city)
    state = clean(partner.state)
    zip_code = clean(partner.postal_code)
    city_state_zip = ""
    if city or state or zip_code:
        city_state_zip = f"{city}{', ' if city and state else ''}{state} {zip_code}".strip()

    solicitor_phone = _first_phone(getattr(solicitor, "phone", None), getattr(solicitor, "mobile_phone", None))
    mrpoc_phone = _first_phone(getattr(mrpoc, "phone", None), getattr(mrpoc, "mobile_phone", None))

    return {
        "letter_date": formatted_date,
        "salutation": salutation,
        "contact_first_name": contact_first_name,
        "contact_last_name": contact_last_name,
        "recipient_line": " ".join(
            part for part in (salutation, contact_first_name, contact_last_name) if part
        ).strip(),
        "contact_display_name": contact_display_name,
        "company": clean(partner.partner_name),
        "address_1": clean(partner.address_1),
        "address_2": clean(partner.address_2),
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "city_state_zip": city_state_zip,
        "amount_requested": _format_currency(amount_requested),
        "amount_requested_no_symbol": _format_currency(amount_requested).replace("$", ""),
        "solicitor_name": _person_name(solicitor),
        "solicitor_number": normalize_phone(solicitor_phone),
        "solicitor_email": clean(getattr(solicitor, "email", None)),
        "mr_contact": _person_name(mrpoc),
        "mr_contact_phone": normalize_phone(mrpoc_phone),
        "mr_contact_email": clean(getattr(mrpoc, "email", None)),
        "dear_line": dear_line or "Sir or Madam",
        "cc_line": f"cc: {_person_name(mrpoc)}".strip(),
    }


def generate_solicitation_pdf_bytes(context: dict) -> bytes:
    from app.services.letters.solicitation import (
        _SIGNATURE_RELATIVE_PATH,
        build_solicitation_render_plan,
    )
    letter_template = get_letter_template("solicitation")
    template_path = letter_template.resolve_template_path(app_root_path=current_app.root_path)
    project_root = Path(current_app.root_path).parent
    signature_path = project_root / _SIGNATURE_RELATIVE_PATH
    render_plan = build_solicitation_render_plan(
        context, signature_image_path=signature_path if signature_path.exists() else None
    )
    renderer = DocxTemplateService()
    try:
        return renderer.render_pdf_bytes(template_path=template_path, plan=render_plan)
    except DocxTemplateError as exc:
        raise SolicitationLetterError(str(exc)) from exc


def build_solicitation_mailing_list_text(solicitations: list[Solicitation]) -> str:
    blocks = [
        _solicitation_envelope_block(solicitation)
        for solicitation in solicitations
    ]
    blocks = [block for block in blocks if block]
    return "\n\n".join(blocks)


def _pick_contact(contacts: list[Contact]) -> Contact | None:
    if not contacts:
        return None
    ranked = sorted(
        contacts,
        key=lambda item: (
            not item.is_primary,
            not item.is_active,
            (item.last_name or "").lower(),
            (item.first_name or "").lower(),
            item.id,
        ),
    )
    return ranked[0]


def _solicitation_envelope_block(solicitation: Solicitation) -> str:
    partner = solicitation.partner
    if partner is None:
        return ""

    contact = _pick_contact(partner.contacts)

    contact_first_name = clean(contact.first_name if contact else None)
    contact_last_name = clean(contact.last_name if contact else None)
    contact_display_name = " ".join(
        part for part in (contact_first_name, contact_last_name) if part
    )

    city = clean(partner.city)
    state = clean(partner.state)
    zip_code = clean(partner.postal_code)
    city_state_zip = ""
    if city or state or zip_code:
        city_state_zip = f"{city}{', ' if city and state else ''}{state} {zip_code}".strip()

    lines = []
    if contact_display_name:
        lines.append(contact_display_name)
    company = clean(partner.partner_name)
    if company:
        lines.append(company)
    address_1 = clean(partner.address_1)
    if address_1:
        lines.append(address_1)
    address_2 = clean(partner.address_2)
    if address_2:
        lines.append(address_2)
    if city_state_zip:
        lines.append(city_state_zip)

    return "\n".join(lines)


def _person_name(person) -> str:
    if person is None:
        return ""
    first_name = clean(getattr(person, "preferred_name", None) or getattr(person, "first_name", None))
    last_name = clean(getattr(person, "last_name", None))
    return " ".join(part for part in (first_name, last_name) if part)


def _format_currency(value: Decimal | None) -> str:
    if value is None:
        return "(amount)"
    return f"${value:,.2f}"


def _first_phone(*values: str | None) -> str:
    for value in values:
        cleaned = clean(value)
        if cleaned:
            return cleaned
    return ""
