import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Campaign, Partner, Person, Solicitation, User


class SolicitationDeleteTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_sol_delete_"))

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
            db.session.add(user)

            solicitor = Person(
                first_name="Alex",
                last_name="Adams",
                email="alex@example.com",
                phone="4105551212",
            )
            db.session.add(solicitor)

            campaign = Campaign(
                campaign_year=2026,
                campaign_name="2026 Campaign",
                status="active",
            )
            db.session.add(campaign)
            db.session.flush()

            partner_a = Partner(
                partner_name="Alpha Corp",
                partner_type="Finance",
                address_1="1 Main St",
                city="Baltimore",
                state="MD",
                postal_code="21201",
            )
            partner_b = Partner(
                partner_name="Beta Corp",
                partner_type="Finance",
                address_1="2 Main St",
                city="Baltimore",
                state="MD",
                postal_code="21201",
            )
            db.session.add_all([partner_a, partner_b])
            db.session.flush()

            # Solicitation eligible for deletion (status = not_contacted)
            sol_deletable = Solicitation(
                partner_id=partner_a.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor.id,
                status="not_contacted",
            )
            # Solicitation NOT eligible (status = contacted)
            sol_not_deletable = Solicitation(
                partner_id=partner_b.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor.id,
                status="contacted",
            )
            db.session.add_all([sol_deletable, sol_not_deletable])
            db.session.commit()

            self.user_id = str(user.id)
            self.solicitor_id = solicitor.id
            self.deletable_id = sol_deletable.id
            self.not_deletable_id = sol_not_deletable.id

        with self.client.session_transaction() as sess:
            sess["_user_id"] = self.user_id
            sess["_fresh"] = True

    # --- Model property ---

    def test_can_delete_true_for_not_contacted(self):
        with self.app.app_context():
            sol = db.session.get(Solicitation, self.deletable_id)
            self.assertTrue(sol.can_delete)

    def test_can_delete_false_for_other_statuses(self):
        with self.app.app_context():
            sol = db.session.get(Solicitation, self.not_deletable_id)
            self.assertFalse(sol.can_delete)

    # --- Confirm page ---

    def test_confirm_page_shown_for_deletable_solicitation(self):
        response = self.client.get(f"/solicitations/{self.deletable_id}/delete")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Delete Solicitation", html)
        self.assertIn("Alpha Corp", html)

    def test_confirm_page_redirects_for_non_deletable_solicitation(self):
        response = self.client.get(f"/solicitations/{self.not_deletable_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/solicitations/{self.not_deletable_id}/edit", response.headers["Location"])

    # --- Delete route ---

    def test_delete_removes_deletable_solicitation(self):
        response = self.client.post(f"/solicitations/{self.deletable_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/solicitations", response.headers["Location"])

        with self.app.app_context():
            sol = db.session.get(Solicitation, self.deletable_id)
            self.assertIsNone(sol)

    def test_delete_rejects_non_deletable_solicitation(self):
        response = self.client.post(f"/solicitations/{self.not_deletable_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/solicitations/{self.not_deletable_id}/edit", response.headers["Location"])

        with self.app.app_context():
            sol = db.session.get(Solicitation, self.not_deletable_id)
            self.assertIsNotNone(sol)

    def test_cancel_leaves_solicitation_unchanged(self):
        # Visiting the confirm page (GET) and then navigating away (not POSTing)
        self.client.get(f"/solicitations/{self.deletable_id}/delete")

        with self.app.app_context():
            sol = db.session.get(Solicitation, self.deletable_id)
            self.assertIsNotNone(sol)
            self.assertEqual(sol.status, "not_contacted")

    def test_edit_page_shows_delete_button_for_deletable(self):
        response = self.client.get(f"/solicitations/{self.deletable_id}/edit")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Danger Zone", html)
        self.assertIn(f"/solicitations/{self.deletable_id}/delete", html)
        self.assertNotIn("historical record", html)

    def test_edit_page_shows_disabled_button_for_non_deletable(self):
        response = self.client.get(f"/solicitations/{self.not_deletable_id}/edit")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Danger Zone", html)
        self.assertIn("historical record", html)
        self.assertNotIn(f"/solicitations/{self.not_deletable_id}/delete", html)
