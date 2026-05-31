#!/usr/bin/env python3
"""
Export Partner records to a lightweight JSON seed file.
"""

from __future__ import annotations

import json
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import Partner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "seeds" / "partners.json"


def main() -> int:
    app = create_app()
    with app.app_context():
        db.create_all()
        partners = db.session.query(Partner).order_by(
            Partner.partner_name.asc(),
            Partner.display_name.asc(),
            Partner.id.asc(),
        ).all()

        payload = []
        for partner in partners:
            payload.append(
                {
                    "display_name": partner.display_name,
                    "partner_name": partner.partner_name,
                    "partner_type": partner.partner_type,
                    "address_1": partner.address_1,
                    "address_2": partner.address_2,
                    "city": partner.city,
                    "state": partner.state,
                    "postal_code": partner.postal_code,
                    "phone_main": partner.phone_main,
                    "email_main": partner.email_main,
                    "notes": partner.partner_notes,
                    "is_active": partner.is_active,
                }
            )

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        print(f"Partners exported: {len(payload)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
