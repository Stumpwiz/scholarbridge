#!/usr/bin/env python3
"""
Import Partner records from a lightweight JSON seed file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app import create_app
from app.db_safety import require_data_mutation_opt_in
from app.extensions import db
from app.models import Partner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "seeds" / "partners.json"

TEXT_FIELDS = (
    "display_name",
    "partner_name",
    "partner_type",
    "address_1",
    "address_2",
    "city",
    "state",
    "postal_code",
    "phone_main",
    "email_main",
    "notes",
)


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped if stripped else None


def _clean_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = _normalize(value)
    if normalized in {"false", "0", "no", "off"}:
        return False
    if normalized in {"true", "1", "yes", "on"}:
        return True
    return default


def _partner_match_key(payload: dict[str, Any]) -> str:
    return _normalize(payload.get("partner_name"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import Partner records from data/seeds/partners.json."
    )
    parser.add_argument(
        "--allow-data-mutation",
        action="store_true",
        help="Explicitly allow database writes for this import run.",
    )
    args = parser.parse_args()

    require_data_mutation_opt_in(
        "import partner seed data",
        allow_flag=args.allow_data_mutation,
    )

    if not INPUT_PATH.exists():
        print(f"ERROR: Seed file not found: {INPUT_PATH}")
        return 1

    try:
        data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {INPUT_PATH}: {exc}")
        return 1

    if not isinstance(data, list):
        print(f"ERROR: Expected a JSON array in {INPUT_PATH}")
        return 1

    app = create_app()
    with app.app_context():
        db.create_all()
        existing_partners = db.session.query(Partner).all()
        existing_keys = {
            _partner_match_key({"partner_name": partner.partner_name})
            for partner in existing_partners
        }

        created = 0
        skipped = 0
        seen_keys = set()

        for raw_item in data:
            if not isinstance(raw_item, dict):
                skipped += 1
                continue

            record = {field: _clean_text(raw_item.get(field)) for field in TEXT_FIELDS}
            record["is_active"] = _clean_bool(raw_item.get("is_active"), default=True)
            match_key = _partner_match_key(record)

            # Sparse-data-friendly guardrail: partner_name is the only required field.
            if not match_key:
                skipped += 1
                continue

            if match_key in seen_keys or match_key in existing_keys:
                skipped += 1
                continue

            partner = Partner(
                display_name=record["display_name"],
                partner_name=record["partner_name"],
                partner_type=record["partner_type"],
                address_1=record["address_1"],
                address_2=record["address_2"],
                city=record["city"],
                state=record["state"],
                postal_code=record["postal_code"],
                phone_main=record["phone_main"],
                email_main=record["email_main"],
                partner_notes=record["notes"],
                is_active=record["is_active"],
            )
            db.session.add(partner)
            seen_keys.add(match_key)
            existing_keys.add(match_key)
            created += 1

        db.session.commit()

        print(f"Partners created: {created}")
        print(f"Partners skipped: {skipped}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
