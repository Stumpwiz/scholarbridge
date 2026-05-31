#!/usr/bin/env python3
"""
Export Person records to a lightweight JSON seed file.
"""

from __future__ import annotations

import json
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import Person

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "seeds" / "people.json"

EXPORT_FIELDS = (
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


def main() -> int:
    app = create_app()
    with app.app_context():
        db.create_all()
        people = db.session.query(Person).order_by(
            Person.last_name.asc(),
            Person.first_name.asc(),
            Person.id.asc(),
        ).all()

        payload = []
        for person in people:
            payload.append({field: getattr(person, field) for field in EXPORT_FIELDS})

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        print(f"People exported: {len(payload)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
