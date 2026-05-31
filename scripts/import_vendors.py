#!/usr/bin/env python3
"""
Bootstrap importer for vendor partners and contacts.

Scope is intentionally narrow:
- Read vendors.xlsx style spreadsheets.
- Import Partners and Contacts only.
- Provide optional non-destructive reset and dry-run behavior.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import Contact, Partner


MISSING_TOKENS = {"", "na", "n/a", "none", "null", "-", "--"}
PARTNER_TYPE_OPTIONS = {
    "Food and Beverage",
    "Finance",
    "Insurance",
    "Accounting",
    "HR",
    "IT",
    "Security Services",
    "Construction",
    "Renovation",
    "Moving",
    "Packing",
    "Medical Service Providers",
    "Personal Service Providers",
    "Cleaning Services and Supplies",
    "Admin",
    "Needs Review",
}

SHEET_SKIP = {"Export Summary"}
FULL_NAME_RE = re.compile(r"^\s*(?P<name>[^,(]+?)(?:,\s*(?P<title>.+))?\s*$")


@dataclass
class RowPayload:
    sheet_name: str
    row_index: int
    partner_name: str | None
    address_1: str | None
    address_2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    partner_email: str | None
    partner_phone: str | None
    first_name: str | None
    last_name: str | None
    title: str | None
    email: str | None
    phone: str | None
    raw_full_name: str | None
    partner_type: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap import Partners and Contacts from a vendor spreadsheet."
    )
    parser.add_argument(
        "spreadsheet",
        nargs="?",
        default="data/original/vendors.xlsx",
        help="Path to spreadsheet file (default: data/original/vendors.xlsx).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete Contacts then Partners before import. Campaigns/Users/Persons are preserved.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and summarize intended actions without writing database changes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spreadsheet_path = Path(args.spreadsheet)
    if not spreadsheet_path.is_absolute():
        spreadsheet_path = PROJECT_ROOT / spreadsheet_path

    if not spreadsheet_path.exists():
        print(f"ERROR: Spreadsheet not found: {spreadsheet_path}")
        return 1

    app = create_app()
    with app.app_context():
        db.create_all()
        importer = VendorBootstrapImporter(
            spreadsheet_path=spreadsheet_path,
            reset=args.reset,
            dry_run=args.dry_run,
        )
        importer.run()

    return 0


class VendorBootstrapImporter:
    def __init__(self, spreadsheet_path: Path, reset: bool, dry_run: bool):
        self.spreadsheet_path = spreadsheet_path
        self.reset = reset
        self.dry_run = dry_run

        self.partner_created = 0
        self.partner_skipped = 0
        self.partner_skip_reasons: Counter[str] = Counter()

        self.contact_created = 0
        self.contact_skipped = 0
        self.contact_skip_reasons: Counter[str] = Counter()

        self._partner_cache: dict[str, Partner] = {}
        self._contact_keys_by_partner: dict[int, set[tuple[str, str, str, str, str]]] = {}

    def run(self) -> None:
        print(f"Workbook: {self.spreadsheet_path}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'IMPORT'}")
        if self.reset:
            self._reset_data()

        self._prime_existing_indexes()

        workbook = pd.ExcelFile(self.spreadsheet_path)
        total_rows = 0
        for sheet_name in workbook.sheet_names:
            if sheet_name in SHEET_SKIP:
                continue
            df = workbook.parse(sheet_name)
            imported_rows = self._import_sheet(df, sheet_name)
            total_rows += imported_rows

        if self.dry_run:
            db.session.rollback()
        else:
            db.session.commit()

        self._print_summary(total_rows)

    def _reset_data(self) -> None:
        contact_count = db.session.query(Contact).delete(synchronize_session=False)
        partner_count = db.session.query(Partner).delete(synchronize_session=False)
        if self.dry_run:
            db.session.rollback()
        else:
            db.session.commit()
        mode_prefix = "[DRY-RUN] " if self.dry_run else ""
        print(
            f"{mode_prefix}Reset complete: deleted {contact_count} contacts and "
            f"{partner_count} partners."
        )

    def _prime_existing_indexes(self) -> None:
        for partner in db.session.query(Partner).all():
            key = normalize_key(partner.partner_name)
            if key:
                self._partner_cache[key] = partner

        for contact in db.session.query(Contact).all():
            contact_key = make_contact_key(
                first_name=contact.first_name,
                last_name=contact.last_name,
                title=contact.title,
                email=contact.email,
                phone=contact.phone,
            )
            self._contact_keys_by_partner.setdefault(contact.partner_id, set()).add(contact_key)

    def _import_sheet(self, df: pd.DataFrame, sheet_name: str) -> int:
        imported_rows = 0
        for row_index, raw_row in enumerate(df.to_dict(orient="records"), start=2):
            payload = self._row_payload(raw_row, sheet_name=sheet_name, row_index=row_index)
            if payload.partner_name is None:
                self._skip_partner("blank_partner_name")
                continue

            partner, created = self._get_or_create_partner(payload)
            if created:
                self.partner_created += 1
            else:
                self._skip_partner("existing_partner")

            self._create_contact_if_present(partner, payload)
            imported_rows += 1
        return imported_rows

    def _row_payload(self, row: dict[str, Any], sheet_name: str, row_index: int) -> RowPayload:
        company = clean_text(row.get("Company"))
        address_1 = clean_text(row.get("Address 1 "))
        address_2 = clean_text(row.get("Address 2 "))
        city = clean_text(row.get("City "))
        state = clean_text(row.get("State "))
        postal_code = clean_text(row.get("Zip"))
        partner_email = clean_text(row.get("Email"))
        partner_phone = clean_text(row.get("Phone"))

        first_name = clean_text(row.get("Contact  First Name"))
        last_name = clean_text(row.get("Contact Last Name"))
        title = None
        full_name = clean_text(row.get("Contact full name with title"))
        source_category = (
            clean_text(row.get("Partner Category"))
            or clean_text(row.get("Category"))
            or clean_text(row.get("Type"))
        )

        if full_name and not (first_name or last_name):
            parsed_name, parsed_title = parse_full_name_and_title(full_name)
            first_name = parsed_name[0] if parsed_name else None
            last_name = parsed_name[1] if parsed_name else None
            title = parsed_title

        return RowPayload(
            sheet_name=sheet_name,
            row_index=row_index,
            partner_name=company,
            address_1=address_1,
            address_2=address_2,
            city=city,
            state=state,
            postal_code=postal_code,
            partner_email=partner_email,
            partner_phone=partner_phone,
            first_name=first_name,
            last_name=last_name,
            title=title,
            email=clean_text(row.get("Email")),
            phone=clean_text(row.get("Phone")),
            raw_full_name=full_name,
            partner_type=normalize_partner_type(source_category),
        )

    def _get_or_create_partner(self, payload: RowPayload) -> tuple[Partner, bool]:
        assert payload.partner_name is not None
        partner_key = normalize_key(payload.partner_name)
        existing = self._partner_cache.get(partner_key)
        if existing:
            self._backfill_partner_fields(existing, payload)
            return existing, False

        partner = Partner(
            partner_name=payload.partner_name,
            partner_type=payload.partner_type,
            address_1=payload.address_1,
            address_2=payload.address_2,
            city=payload.city,
            state=payload.state,
            postal_code=payload.postal_code,
            email_main=payload.partner_email,
            phone_main=payload.partner_phone,
            is_active=True,
        )
        db.session.add(partner)
        db.session.flush()

        self._partner_cache[partner_key] = partner
        return partner, True

    def _backfill_partner_fields(self, partner: Partner, payload: RowPayload) -> None:
        updates = (
            ("partner_type", payload.partner_type),
            ("address_1", payload.address_1),
            ("address_2", payload.address_2),
            ("city", payload.city),
            ("state", payload.state),
            ("postal_code", payload.postal_code),
            ("email_main", payload.partner_email),
            ("phone_main", payload.partner_phone),
        )
        for field_name, value in updates:
            if value and not getattr(partner, field_name):
                setattr(partner, field_name, value)

    def _create_contact_if_present(self, partner: Partner, payload: RowPayload) -> None:
        if not has_contact_identity(payload):
            self._skip_contact("insufficient_identifying_information")
            return

        contact_key = make_contact_key(
            first_name=payload.first_name,
            last_name=payload.last_name,
            title=payload.title,
            email=payload.email,
            phone=payload.phone,
        )
        existing_keys = self._contact_keys_by_partner.setdefault(partner.id, set())
        if contact_key in existing_keys:
            self._skip_contact("duplicate_contact_for_partner")
            return

        is_primary = self._should_assign_primary(partner.id)
        contact = Contact(
            partner_id=partner.id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            title=payload.title,
            email=payload.email,
            phone=payload.phone,
            notes=None,
            is_primary=is_primary,
            is_active=True,
        )
        db.session.add(contact)
        existing_keys.add(contact_key)
        self.contact_created += 1

    def _should_assign_primary(self, partner_id: int) -> bool:
        if partner_id not in self._contact_keys_by_partner:
            return True
        existing_primary = db.session.query(Contact).filter_by(
            partner_id=partner_id, is_primary=True
        ).first()
        return existing_primary is None and not self._contact_keys_by_partner[partner_id]

    def _skip_partner(self, reason: str) -> None:
        self.partner_skipped += 1
        self.partner_skip_reasons[reason] += 1

    def _skip_contact(self, reason: str) -> None:
        self.contact_skipped += 1
        self.contact_skip_reasons[reason] += 1

    def _print_summary(self, total_rows: int) -> None:
        mode_prefix = "[DRY-RUN] " if self.dry_run else ""
        print()
        print(f"{mode_prefix}Processed rows: {total_rows}")
        print(f"{mode_prefix}Partners created: {self.partner_created}")
        print(f"{mode_prefix}Partners skipped: {self.partner_skipped}")
        for reason, count in sorted(self.partner_skip_reasons.items()):
            print(f"  - {reason}: {count}")
        print(f"{mode_prefix}Contacts created: {self.contact_created}")
        print(f"{mode_prefix}Contacts skipped: {self.contact_skipped}")
        for reason, count in sorted(self.contact_skip_reasons.items()):
            print(f"  - {reason}: {count}")


def clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in MISSING_TOKENS:
        return None
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_key(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())


def parse_full_name_and_title(full_name: str) -> tuple[tuple[str | None, str | None], str | None]:
    match = FULL_NAME_RE.match(full_name)
    if not match:
        return (None, None), None
    name_part = clean_text(match.group("name"))
    title_part = clean_text(match.group("title"))
    if not name_part:
        return (None, None), title_part
    parts = name_part.split(" ")
    if len(parts) == 1:
        return (parts[0], None), title_part
    return (parts[0], " ".join(parts[1:])), title_part


def has_contact_identity(payload: RowPayload) -> bool:
    return any(
        [
            payload.first_name,
            payload.last_name,
            payload.email,
            payload.phone,
            payload.raw_full_name,
        ]
    )


def make_contact_key(
    first_name: str | None,
    last_name: str | None,
    title: str | None,
    email: str | None,
    phone: str | None,
) -> tuple[str, str, str, str, str]:
    return (
        normalize_key(first_name),
        normalize_key(last_name),
        normalize_key(title),
        normalize_key(email),
        normalize_phone(phone),
    )


def normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    return digits or normalize_key(phone)


def normalize_partner_type(raw_category: str | None) -> str | None:
    if raw_category is None:
        return None
    if raw_category in PARTNER_TYPE_OPTIONS:
        return raw_category
    return "Needs Review"


if __name__ == "__main__":
    raise SystemExit(main())
