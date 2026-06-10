from __future__ import annotations

import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import current_app, render_template
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Campaign, Contact, Partner, Solicitation


class SolicitationLetterError(RuntimeError):
    """Raised when solicitation letter generation fails."""


def build_solicitation_letter_context(partner_id: int) -> dict:
    partner = db.session.scalar(
        select(Partner)
        .options(selectinload(Partner.contacts))
        .where(Partner.id == partner_id)
    )
    if partner is None:
        raise SolicitationLetterError("Partner not found.")

    contact = _pick_contact(partner.contacts)
    solicitation = _pick_solicitation(partner.id)
    return _build_solicitation_letter_context(partner, contact, solicitation)


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

    today = date.today()
    formatted_date = f"{today.strftime('%B')} {today.day}, {today.year}"
    logo_path = (
        Path(current_app.root_path) / "static" / "img" / "branding" / "scholarshipProgramLogo.png"
    )

    salutation = _clean(contact.title if contact else None)
    contact_first_name = _clean(contact.first_name if contact else None)
    contact_last_name = _clean(contact.last_name if contact else None)
    contact_display_name = " ".join(
        part for part in (salutation, contact_first_name, contact_last_name) if part
    )
    dear_salutation = salutation or "Sir or Madam"
    dear_last_name = contact_last_name or ""
    dear_line = " ".join(part for part in (dear_salutation, dear_last_name) if part).strip()

    context = {
        "letter_date": formatted_date,
        "salutation": salutation,
        "contact_first_name": contact_first_name,
        "contact_last_name": contact_last_name,
        "contact_display_name": contact_display_name,
        "company": _clean(partner.partner_name),
        "address_1": _clean(partner.address_1),
        "address_2": _clean(partner.address_2),
        "city": _clean(partner.city),
        "state": _clean(partner.state),
        "zip_code": _clean(partner.postal_code),
        "amount_requested": _format_currency(amount_requested),
        "solicitor_name": _person_name(solicitor),
        "solicitor_number": _clean(getattr(solicitor, "phone", None) or getattr(solicitor, "mobile_phone", None)),
        "solicitor_email": _clean(getattr(solicitor, "email", None)),
        "mr_contact": _person_name(mrpoc),
        "dear_line": dear_line or "Sir or Madam",
        "logo_path": logo_path.as_posix(),
    }
    return {key: _latex_escape(str(value)) for key, value in context.items()}


def generate_solicitation_pdf_bytes(context: dict) -> bytes:
    rendered_tex = render_template("letters/solicitation.tex.j2", **context)

    with TemporaryDirectory(prefix="scholarbridge-letter-") as temp_dir:
        temp_path = Path(temp_dir)
        tex_file = temp_path / "solicitation.tex"
        tex_file.write_text(rendered_tex, encoding="utf-8")

        result = subprocess.run(
            [
                "xelatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "solicitation.tex",
            ],
            cwd=temp_path,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
            raise SolicitationLetterError(f"XeLaTeX failed while generating the PDF.\n{output}")

        pdf_path = temp_path / "solicitation.pdf"
        if not pdf_path.exists():
            raise SolicitationLetterError("XeLaTeX completed but did not produce a PDF.")

        return pdf_path.read_bytes()


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


def _pick_solicitation(partner_id: int) -> Solicitation | None:
    return db.session.scalar(
        select(Solicitation)
        .options(
            selectinload(Solicitation.campaign),
            selectinload(Solicitation.solicitor),
            selectinload(Solicitation.mrpoc),
        )
        .join(Campaign, Campaign.id == Solicitation.campaign_id)
        .where(Solicitation.partner_id == partner_id)
        .order_by(Campaign.campaign_year.desc(), Solicitation.id.desc())
    )


def _person_name(person) -> str:
    if person is None:
        return ""
    first_name = _clean(getattr(person, "preferred_name", None) or getattr(person, "first_name", None))
    last_name = _clean(getattr(person, "last_name", None))
    return " ".join(part for part in (first_name, last_name) if part)


def _format_currency(value: Decimal | None) -> str:
    if value is None:
        return "(amount)"
    return f"${value:,.2f}"


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)
