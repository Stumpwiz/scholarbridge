import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Campaign, Partner, Person, Solicitation, User


class LettersQueueTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_letters_queue_"))

        class TestConfig(Config):
            SECRET_KEY = "test-secret"
            TESTING = True
            DATABASE_URL = f"sqlite:///{self._tmp_dir / 'test.db'}"

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
            db.session.add(user)

            solicitor_a = Person(first_name="Alex", last_name="Adams")
            solicitor_b = Person(first_name="Blair", last_name="Baker")
            db.session.add_all([solicitor_a, solicitor_b])

            campaign = Campaign(
                campaign_year=2026,
                campaign_name="2026 Scholarship Campaign",
                status="active",
            )
            db.session.add(campaign)
            db.session.flush()

            partner_ready = Partner(partner_name="Zulu Partner", display_name="Alpha Display", partner_type="Finance")
            partner_incomplete = Partner(partner_name="Bravo Partner", partner_type=None)
            partner_incomplete_2 = Partner(partner_name="Delta Partner", partner_type=None)
            partner_ready_no_display = Partner(partner_name="Beta Partner", display_name=None, partner_type="Insurance")
            db.session.add_all(
                [
                    partner_ready,
                    partner_incomplete,
                    partner_incomplete_2,
                    partner_ready_no_display,
                ]
            )
            db.session.flush()

            solicitation_ready_1 = Solicitation(
                partner_id=partner_ready.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_a.id,
                business_volume=5000,
                amount_requested=1250,
            )
            solicitation_incomplete = Solicitation(
                partner_id=partner_incomplete.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_a.id,
                business_volume=4000,
                amount_requested=1000,
            )
            solicitation_ready_2 = Solicitation(
                partner_id=partner_ready_no_display.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_b.id,
                business_volume=2200,
                amount_requested=700,
            )
            solicitation_incomplete_2 = Solicitation(
                partner_id=partner_incomplete_2.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_b.id,
                business_volume=3300,
                amount_requested=950,
            )
            db.session.add_all(
                [
                    solicitation_ready_1,
                    solicitation_incomplete,
                    solicitation_ready_2,
                    solicitation_incomplete_2,
                ]
            )
            db.session.commit()

            self.user_id = str(user.id)
            self.solicitor_a_id = solicitor_a.id
            self.solicitor_b_id = solicitor_b.id
            self.ready_id = solicitation_ready_1.id
            self.incomplete_id = solicitation_incomplete.id
            self.ready_2_id = solicitation_ready_2.id
            self.incomplete_2_id = solicitation_incomplete_2.id

        with self.client.session_transaction() as session:
            session["_user_id"] = self.user_id
            session["_fresh"] = True

    def test_letters_queue_orders_incomplete_before_ready_and_preserves_alpha_within_groups(self):
        response = self.client.get("/letters")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        first_alpha = html.find("Alpha Display")
        first_beta_partner = html.find("Beta Partner")
        first_bravo_partner = html.find("Bravo Partner")
        first_delta_partner = html.find("Delta Partner")
        self.assertTrue(first_bravo_partner < first_delta_partner < first_alpha < first_beta_partner)

    def test_letters_queue_filters_by_solicitor(self):
        response = self.client.get(f"/letters?solicitor_id={self.solicitor_b_id}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Beta Partner", html)
        self.assertIn("Delta Partner", html)
        self.assertNotIn("Alpha Display", html)
        self.assertNotIn("Bravo Partner", html)
        self.assertTrue(html.find("Delta Partner") < html.find("Beta Partner"))

    def test_letters_queue_shows_incomplete_and_ready_statuses(self):
        response = self.client.get("/letters")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('<span class="badge text-bg-warning">Incomplete</span>', html)
        self.assertIn('<span class="badge text-bg-success">Ready</span>', html)

    def test_letters_queue_action_availability_uses_readiness(self):
        response = self.client.get("/letters")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn(f"/letters/solicitation.pdf?solicitation_id={self.ready_id}", html)
        self.assertIn("Generate Letter", html)
        self.assertIn(f"/solicitations/{self.incomplete_id}/edit", html)
        self.assertIn("View/Edit Solicitation", html)

    def test_letter_generation_is_blocked_for_non_ready_solicitation(self):
        response = self.client.get(
            f"/letters/solicitation.pdf?solicitation_id={self.incomplete_id}",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Solicitation is incomplete.", html)
        self.assertIn("Update solicitation details before generating a letter.", html)
        self.assertIn("Edit Solicitation", html)

    def test_letter_generation_allowed_for_ready_solicitation(self):
        with patch("app.main.routes.generate_solicitation_pdf_bytes", return_value=b"%PDF-test"):
            response = self.client.get(
                f"/letters/solicitation.pdf?solicitation_id={self.ready_id}"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertEqual(response.data, b"%PDF-test")


if __name__ == "__main__":
    unittest.main()
