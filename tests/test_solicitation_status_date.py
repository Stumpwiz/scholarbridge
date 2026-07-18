import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Campaign, Partner, Person, Solicitation, User


class SolicitationStatusDateTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_sol_status_date_"))

        class TestConfig(Config):
            SECRET_KEY = "test-secret"
            TESTING = True
            DATABASE_URL = f"sqlite:///{self._tmp_dir / 'test.db'}"
            GENERATED_LETTERS_DIR = str(self._tmp_dir / "generated_letters")

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            user = User(
                username="editor",
                email="editor@example.com",
                role=User.ROLE_EDITOR,
                is_active=True,
            )
            user.set_password("password123")
            solicitor = Person(
                first_name="Alex",
                last_name="Adams",
                email="alex@example.com",
                phone="4105551212",
            )
            campaign = Campaign(
                campaign_year=2026,
                campaign_name="2026 Campaign",
                status="active",
            )
            partner = Partner(
                partner_name="Alpha Corp",
                partner_type="Finance",
                address_1="1 Main St",
                city="Baltimore",
                state="MD",
                postal_code="21201",
            )
            db.session.add_all([user, solicitor, campaign, partner])
            db.session.flush()

            solicitation = Solicitation(
                partner_id=partner.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor.id,
                mrpoc_person_id=solicitor.id,
                tranche=1,
                business_volume=5000,
                amount_requested=1000,
                amount_pledged=0,
                status="not_contacted",
            )
            db.session.add(solicitation)
            db.session.commit()

            self.user_id = str(user.id)
            self.solicitor_id = solicitor.id
            self.campaign_id = campaign.id
            self.partner_id = partner.id
            self.solicitation_id = solicitation.id

        with self.client.session_transaction() as session:
            session["_user_id"] = self.user_id
            session["_fresh"] = True

    def _edit_data(self, **overrides):
        data = {
            "campaign_id": str(self.campaign_id),
            "partner_id": str(self.partner_id),
            "solicitor_person_id": str(self.solicitor_id),
            "mrpoc_person_id": str(self.solicitor_id),
            "tranche": "1",
            "business_volume": "5000.00",
            "amount_requested": "1000.00",
            "amount_pledged": "0.00",
            "amount_received": "",
            "status": "not_contacted",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_solicitation_creation_leaves_status_date_null(self):
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.solicitation_id)
            self.assertEqual(solicitation.status, "not_contacted")
            self.assertIsNone(solicitation.status_date)

    def test_changing_status_sets_status_date_to_today(self):
        with patch("app.main.solicitation_workflow.date") as workflow_date:
            workflow_date.today.return_value = date(2026, 7, 18)
            response = self.client.post(
                f"/solicitations/{self.solicitation_id}/edit",
                data=self._edit_data(status="contacted"),
            )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.solicitation_id)
            self.assertEqual(solicitation.status, "contacted")
            self.assertEqual(solicitation.status_date, date(2026, 7, 18))

    def test_editing_other_fields_with_unchanged_status_leaves_status_date_unchanged(self):
        original_date = date(2026, 7, 10)
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.solicitation_id)
            solicitation.status_date = original_date
            db.session.commit()

        response = self.client.post(
            f"/solicitations/{self.solicitation_id}/edit",
            data=self._edit_data(notes="Updated notes only"),
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.solicitation_id)
            self.assertEqual(solicitation.notes, "Updated notes only")
            self.assertEqual(solicitation.status, "not_contacted")
            self.assertEqual(solicitation.status_date, original_date)

    def test_repeated_edits_with_unchanged_status_preserve_original_status_date(self):
        original_date = date(2026, 7, 10)
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.solicitation_id)
            solicitation.status = "contacted"
            solicitation.status_date = original_date
            db.session.commit()

        first_response = self.client.post(
            f"/solicitations/{self.solicitation_id}/edit",
            data=self._edit_data(status="contacted", notes="First update"),
        )
        second_response = self.client.post(
            f"/solicitations/{self.solicitation_id}/edit",
            data=self._edit_data(status="contacted", amount_pledged="250.00"),
        )

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.solicitation_id)
            self.assertEqual(solicitation.status, "contacted")
            self.assertEqual(solicitation.amount_pledged, 250)
            self.assertEqual(solicitation.status_date, original_date)


if __name__ == "__main__":
    unittest.main()
