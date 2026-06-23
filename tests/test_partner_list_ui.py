import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Campaign, Contact, Partner, Solicitation, User


class PartnerListUiTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_partners_ui_"))

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

            campaign = Campaign(
                campaign_year=2026,
                campaign_name="2026 Scholarship Campaign",
                status="active",
            )
            db.session.add(campaign)
            db.session.flush()

            active_alpha = Partner(partner_name="Alpha Active", partner_type="Finance", is_active=True)
            active_beta = Partner(partner_name="Beta Active", partner_type="Insurance", is_active=True)
            inactive_zeta = Partner(partner_name="Zeta Inactive", partner_type="IT", is_active=False)
            db.session.add_all([active_alpha, active_beta, inactive_zeta])
            db.session.flush()

            db.session.add_all(
                [
                    Contact(
                        partner_id=active_alpha.id,
                        first_name="A",
                        last_name="One",
                        title="Director",
                        is_primary=True,
                    ),
                    Contact(
                        partner_id=inactive_zeta.id,
                        first_name="Z",
                        last_name="One",
                        title="Manager",
                        is_primary=True,
                    ),
                ]
            )

            db.session.add_all(
                [
                    Solicitation(
                        partner_id=active_alpha.id,
                        campaign_id=campaign.id,
                        status="contacted",
                        amount_pledged=0,
                    ),
                    Solicitation(
                        partner_id=active_beta.id,
                        campaign_id=campaign.id,
                        status="responded",
                        amount_pledged=100,
                    ),
                    Solicitation(
                        partner_id=inactive_zeta.id,
                        campaign_id=campaign.id,
                        status="donated",
                        amount_pledged=250,
                    ),
                ]
            )
            db.session.commit()

            self.user_id = str(user.id)
            self.inactive_partner_id = inactive_zeta.id

        with self.client.session_transaction() as session:
            session["_user_id"] = self.user_id
            session["_fresh"] = True

    def test_partners_default_to_active_only_checked(self):
        response = self.client.get("/partners")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('id="active_only"', html)
        self.assertIn('name="active_only"', html)
        self.assertIn("checked", html[html.find('id="active_only"'): html.find('id="active_only"') + 180])

        self.assertIn("Alpha Active", html)
        self.assertIn("Beta Active", html)
        self.assertNotIn("Zeta Inactive", html)

        # Active-only dashboard totals.
        self.assertIn('<div class="fs-3 fw-bold">2</div>', html)  # Total Partners
        self.assertIn('<div class="fs-5 fw-semibold">0</div>', html)  # Inactive
        self.assertIn('<div class="fs-3 fw-bold text-primary">0</div>', html)  # Gift Received

    def test_partners_unchecked_shows_all_and_updates_totals(self):
        response = self.client.get("/partners?active_only_applied=1")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Alpha Active", html)
        self.assertIn("Beta Active", html)
        self.assertIn("Zeta Inactive", html)

        self.assertNotIn(
            "checked",
            html[html.find('id="active_only"'): html.find('id="active_only"') + 180],
        )

        # All-partner dashboard totals.
        self.assertIn('<div class="fs-3 fw-bold">3</div>', html)  # Total Partners
        self.assertIn('<div class="fs-5 fw-semibold">1</div>', html)  # Inactive
        self.assertIn('<div class="fs-3 fw-bold text-primary">1</div>', html)  # Gift Received

    def test_partners_filter_persists_through_navigation(self):
        response = self.client.get("/partners?active_only_applied=1")
        self.assertEqual(response.status_code, 200)

        detail = self.client.get(f"/partners/{self.inactive_partner_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Zeta Inactive", detail.get_data(as_text=True))

        back_to_list = self.client.get("/partners")
        self.assertEqual(back_to_list.status_code, 200)
        html = back_to_list.get_data(as_text=True)
        self.assertIn("Zeta Inactive", html)
        self.assertNotIn(
            "checked",
            html[html.find('id="active_only"'): html.find('id="active_only"') + 180],
        )


if __name__ == "__main__":
    unittest.main()
