import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Campaign, Partner, Person, Solicitation, User


class SolicitationListUiTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_solicitations_ui_"))

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

            solicitor_a = Person(
                first_name="Alex",
                last_name="Assigned",
                email="alex.assigned@example.com",
                phone="410-555-1100",
            )
            solicitor_b = Person(
                first_name="Blair",
                last_name="Assigned",
                email="blair.assigned@example.com",
                phone="410-555-1101",
            )
            mrpoc_a = Person(
                first_name="Morgan",
                last_name="Ridge",
                email="morgan.ridge@example.com",
                phone="410-555-1102",
            )
            mrpoc_b = Person(
                first_name="Casey",
                last_name="Vale",
                email="casey.vale@example.com",
                phone="410-555-1103",
            )
            db.session.add_all([solicitor_a, solicitor_b, mrpoc_a, mrpoc_b])

            campaign = Campaign(
                campaign_year=2026,
                campaign_name="2026 Scholarship Campaign",
                status="active",
            )
            db.session.add(campaign)
            db.session.flush()

            alpha_ready_partner = Partner(partner_name="Alpha Ready", partner_type="Finance")
            beta_incomplete_partner = Partner(partner_name="Beta Incomplete", partner_type=None)
            delta_incomplete_partner = Partner(partner_name="Delta Incomplete", partner_type="IT")
            gamma_ready_partner = Partner(partner_name="Gamma Ready", partner_type="Insurance")
            db.session.add_all(
                [
                    alpha_ready_partner,
                    beta_incomplete_partner,
                    delta_incomplete_partner,
                    gamma_ready_partner,
                ]
            )
            db.session.flush()

            alpha_ready = Solicitation(
                partner_id=alpha_ready_partner.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_a.id,
                mrpoc_person_id=mrpoc_a.id,
                tranche=1,
                business_volume=5000,
                amount_requested=1000,
            )
            beta_incomplete = Solicitation(
                partner_id=beta_incomplete_partner.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_a.id,
                mrpoc_person_id=mrpoc_a.id,
                tranche=1,
                business_volume=1500,
                amount_requested=300,
            )
            delta_incomplete = Solicitation(
                partner_id=delta_incomplete_partner.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_b.id,
                mrpoc_person_id=mrpoc_b.id,
                tranche=1,
                business_volume=None,
                amount_requested=400,
            )
            gamma_ready = Solicitation(
                partner_id=gamma_ready_partner.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_b.id,
                mrpoc_person_id=mrpoc_b.id,
                tranche=1,
                business_volume=2500,
                amount_requested=None,
            )
            db.session.add_all([alpha_ready, beta_incomplete, delta_incomplete, gamma_ready])
            db.session.commit()

            self.user_id = str(user.id)
            self.solicitor_b_id = solicitor_b.id
            self.ids_by_partner = {
                "Alpha Ready": alpha_ready.id,
                "Beta Incomplete": beta_incomplete.id,
                "Delta Incomplete": delta_incomplete.id,
                "Gamma Ready": gamma_ready.id,
            }

        with self.client.session_transaction() as session:
            session["_user_id"] = self.user_id
            session["_fresh"] = True

    def _row_for_partner(self, html: str, partner_name: str) -> str:
        marker = html.find(partner_name)
        self.assertNotEqual(marker, -1, msg=f"Missing row for partner: {partner_name}")
        row_start = html.rfind("<tr", 0, marker)
        self.assertNotEqual(row_start, -1, msg=f"Missing row start for partner: {partner_name}")
        row_end = html.find("</tr>", marker)
        self.assertNotEqual(row_end, -1, msg=f"Missing row end for partner: {partner_name}")
        return html[row_start : row_end + len("</tr>")]

    def test_solicitations_group_incomplete_first_and_show_new_status_labels(self):
        response = self.client.get("/solicitations")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        first_beta = html.find("Beta Incomplete")
        first_delta = html.find("Delta Incomplete")
        first_alpha = html.find("Alpha Ready")
        first_gamma = html.find("Gamma Ready")
        self.assertTrue(first_beta < first_delta < first_alpha < first_gamma)

        beta_row = self._row_for_partner(html, "Beta Incomplete")
        delta_row = self._row_for_partner(html, "Delta Incomplete")
        alpha_row = self._row_for_partner(html, "Alpha Ready")
        gamma_row = self._row_for_partner(html, "Gamma Ready")

        self.assertIn("table-warning", beta_row)
        self.assertIn("table-warning", delta_row)
        self.assertIn("Incomplete", beta_row)
        self.assertIn("Incomplete", delta_row)
        self.assertNotIn("table-warning", alpha_row)
        self.assertNotIn("table-warning", gamma_row)
        self.assertIn("Ready", alpha_row)
        self.assertIn("Ready", gamma_row)
        self.assertNotIn("Not Contacted", html)

    def test_solicitations_rows_keep_view_and_edit_links(self):
        response = self.client.get("/solicitations")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        for partner_name, solicitation_id in self.ids_by_partner.items():
            row = self._row_for_partner(html, partner_name)
            self.assertIn(f"/solicitations/{solicitation_id}\"", row)
            self.assertIn(f"/solicitations/{solicitation_id}/edit\"", row)

    def test_solicitor_filter_is_preserved_with_grouping(self):
        response = self.client.get(f"/solicitations?solicitor_id={self.solicitor_b_id}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Delta Incomplete", html)
        self.assertIn("Gamma Ready", html)
        self.assertNotIn("Alpha Ready", html)
        self.assertNotIn("Beta Incomplete", html)

        self.assertTrue(html.find("Delta Incomplete") < html.find("Gamma Ready"))


if __name__ == "__main__":
    unittest.main()
