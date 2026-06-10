#!/usr/bin/env python3
"""
Import Person records from a lightweight JSON seed file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app import create_app
from app.db_safety import require_data_mutation_opt_in
from app.extensions import db
from app.models import Person

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "seeds" / "people.json"

IMPORT_FIELDS = (
    "first_name",
    "middle_initial",
    "last_name",
    "preferred_name",
    "email",
    "mobile_phone",
    "other_phone",
    "committee_role",
    "person_notes",
    "is_active",
)


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _person_match_key(payload: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _normalize(payload.get("first_name")),
        _normalize(payload.get("middle_initial")),
        _normalize(payload.get("last_name")),
        _normalize(payload.get("email")),
    )


def _clean_value(payload: dict[str, Any], key: str) -> Any:
    if key == "is_active":
        value = payload.get(key, True)
        if isinstance(value, bool):
            return value
        normalized = _normalize(value)
        if normalized in {"false", "0", "no", "off"}:
            return False
        if normalized in {"true", "1", "yes", "on"}:
            return True
        return True

    value = payload.get(key)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped if stripped else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import Person records from data/seeds/people.json."
    )
    parser.add_argument(
        "--allow-data-mutation",
        action="store_true",
        help="Explicitly allow database writes for this import run.",
    )
    args = parser.parse_args()

    require_data_mutation_opt_in(
        "import people seed data",
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
        existing_people = db.session.query(Person).all()
        existing_keys = {
            _person_match_key(
                {
                    "first_name": person.first_name,
                    "middle_initial": person.middle_initial,
                    "last_name": person.last_name,
                    "email": person.email,
                }
            )
            for person in existing_people
        }

        created = 0
        skipped = 0
        seen_keys = set()

        for raw_item in data:
            if not isinstance(raw_item, dict):
                skipped += 1
                continue

            record = {field: _clean_value(raw_item, field) for field in IMPORT_FIELDS}
            match_key = _person_match_key(record)

            # Basic minimum identity guardrail for sparse but valid Person rows.
            if not match_key[0] or not match_key[2]:
                skipped += 1
                continue

            if match_key in seen_keys or match_key in existing_keys:
                skipped += 1
                continue

            person = Person(
                first_name=record["first_name"],
                middle_initial=record["middle_initial"],
                last_name=record["last_name"],
                preferred_name=record["preferred_name"],
                email=record["email"],
                mobile_phone=record["mobile_phone"],
                other_phone=record["other_phone"],
                phone=record["mobile_phone"] or record["other_phone"],
                committee_role=record["committee_role"],
                person_notes=record["person_notes"],
                is_active=record["is_active"],
            )
            db.session.add(person)
            seen_keys.add(match_key)
            existing_keys.add(match_key)
            created += 1

        db.session.commit()

        print(f"People created: {created}")
        print(f"People skipped: {skipped}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
