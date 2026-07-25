import tempfile
import unittest
from decimal import Decimal
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
            epsilon_new_partner = Partner(partner_name="Epsilon New", partner_type="Accounting")
            db.session.add_all(
                [
                    alpha_ready_partner,
                    beta_incomplete_partner,
                    delta_incomplete_partner,
                    gamma_ready_partner,
                    epsilon_new_partner,
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
                amount_pledged=750,
            )
            beta_incomplete = Solicitation(
                partner_id=beta_incomplete_partner.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_a.id,
                mrpoc_person_id=mrpoc_a.id,
                tranche=2,
                business_volume=1500,
                amount_requested=300,
                amount_pledged=150,
            )
            delta_incomplete = Solicitation(
                partner_id=delta_incomplete_partner.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_b.id,
                mrpoc_person_id=mrpoc_b.id,
                tranche=2,
                business_volume=Decimal("0.00"),
                amount_requested=400,
                amount_pledged=125,
                amount_received=25,
            )
            gamma_ready = Solicitation(
                partner_id=gamma_ready_partner.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_b.id,
                mrpoc_person_id=mrpoc_b.id,
                tranche=3,
                business_volume=2500,
                amount_requested=None,
                amount_pledged=250,
            )
            db.session.add_all([alpha_ready, beta_incomplete, delta_incomplete, gamma_ready])
            db.session.commit()

            self.user_id = str(user.id)
            self.campaign_id = campaign.id
            self.solicitor_a_id = solicitor_a.id
            self.solicitor_b_id = solicitor_b.id
            self.mrpoc_a_id = mrpoc_a.id
            self.ids_by_partner = {
                "Alpha Ready": alpha_ready.id,
                "Beta Incomplete": beta_incomplete.id,
                "Delta Incomplete": delta_incomplete.id,
                "Gamma Ready": gamma_ready.id,
            }
            self.alpha_ready_id = alpha_ready.id
            self.alpha_ready_partner_id = alpha_ready_partner.id
            self.epsilon_new_partner_id = epsilon_new_partner.id

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

    def _requested_amount_select(self, html: str) -> str:
        marker = html.find('id="amount_requested"')
        self.assertNotEqual(marker, -1, msg="Missing requested amount field")
        select_start = html.rfind("<select", 0, marker)
        self.assertNotEqual(select_start, -1, msg="Requested amount field is not a select")
        select_end = html.find("</select>", marker)
        self.assertNotEqual(select_end, -1, msg="Missing requested amount select close")
        return html[select_start : select_end + len("</select>")]

    def _select_for(self, html: str, field_id: str) -> str:
        marker = html.find(f'id="{field_id}"')
        self.assertNotEqual(marker, -1, msg=f"Missing select field: {field_id}")
        select_start = html.rfind("<select", 0, marker)
        self.assertNotEqual(select_start, -1, msg=f"{field_id} field is not a select")
        select_end = html.find("</select>", marker)
        self.assertNotEqual(select_end, -1, msg=f"Missing {field_id} select close")
        return html[select_start : select_end + len("</select>")]

    def test_solicitations_group_incomplete_first_and_show_new_status_labels(self):
        response = self.client.get("/solicitations")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        first_beta = html.find("Beta Incomplete")
        first_delta = html.find("Delta Incomplete")
        first_alpha = html.find("Alpha Ready")
        first_gamma = html.find("Gamma Ready")
        # Not-ready rows appear before ready rows
        self.assertTrue(first_beta < first_alpha or first_delta < first_alpha)
        self.assertTrue(first_gamma < first_alpha)

        beta_row = self._row_for_partner(html, "Beta Incomplete")
        delta_row = self._row_for_partner(html, "Delta Incomplete")
        alpha_row = self._row_for_partner(html, "Alpha Ready")
        gamma_row = self._row_for_partner(html, "Gamma Ready")

        # Beta: partner has no partner_type → Incomplete Partner (red)
        self.assertIn("table-warning", beta_row)
        self.assertIn("Incomplete Partner", beta_row)
        self.assertIn("text-bg-danger", beta_row)

        # Delta: partner complete + zero business_volume + amount_requested → Ready (green)
        self.assertNotIn("table-warning", delta_row)
        self.assertIn("Ready", delta_row)
        self.assertIn("text-bg-success", delta_row)

        # Alpha: partner complete + non-zero business_volume + amount_requested → Ready (green)
        self.assertNotIn("table-warning", alpha_row)
        self.assertIn("Ready", alpha_row)
        self.assertIn("text-bg-success", alpha_row)

        # Gamma: partner complete but amount_requested is None → Incomplete Solicitation (yellow)
        self.assertIn("table-warning", gamma_row)
        self.assertIn("Incomplete Solicitation", gamma_row)
        self.assertIn("text-bg-warning", gamma_row)

        self.assertIn("Not Contacted", html)
        self.assertIn("Pledged", html)
        self.assertIn("$750.00", alpha_row)
        self.assertIn("$5000.00", alpha_row)
        self.assertNotIn("$0.00", delta_row)
        self.assertIn("Amount Requested", html)
        self.assertIn("Amount Pledged", html)
        self.assertIn("Amount Received", html)
        self.assertTrue(
            html.find("Amount Requested")
            < html.find("Amount Pledged")
            < html.find("Amount Received")
        )

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

        self.assertTrue(html.find("Gamma Ready") < html.find("Delta Incomplete"))

    def test_solicitation_filters_show_all_without_filters(self):
        response = self.client.get("/solicitations")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        for partner_name in ("Alpha Ready", "Beta Incomplete", "Delta Incomplete", "Gamma Ready"):
            self.assertIn(partner_name, html)

        solicitor_select = self._select_for(html, "solicitor_id")
        tranche_select = self._select_for(html, "tranche")
        self.assertIn('value="" selected', solicitor_select)
        self.assertIn("All Solicitors", solicitor_select)
        self.assertIn('value="" selected', tranche_select)
        for tranche in ("1", "2", "3"):
            self.assertIn(f'value="{tranche}"', tranche_select)

    def test_solicitation_filter_by_solicitor_only(self):
        response = self.client.get(f"/solicitations?solicitor_id={self.solicitor_a_id}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Alpha Ready", html)
        self.assertIn("Beta Incomplete", html)
        self.assertNotIn("Delta Incomplete", html)
        self.assertNotIn("Gamma Ready", html)
        self.assertIn(f'value="{self.solicitor_a_id}" selected', self._select_for(html, "solicitor_id"))

    def test_solicitation_filter_by_tranche_only(self):
        response = self.client.get("/solicitations?tranche=2")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Beta Incomplete", html)
        self.assertIn("Delta Incomplete", html)
        self.assertNotIn("Alpha Ready", html)
        self.assertNotIn("Gamma Ready", html)
        self.assertIn('value="2" selected', self._select_for(html, "tranche"))

    def test_solicitation_filter_by_solicitor_and_tranche(self):
        response = self.client.get(f"/solicitations?solicitor_id={self.solicitor_b_id}&tranche=2")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Delta Incomplete", html)
        self.assertNotIn("Alpha Ready", html)
        self.assertNotIn("Beta Incomplete", html)
        self.assertNotIn("Gamma Ready", html)
        self.assertIn(f'value="{self.solicitor_b_id}" selected', self._select_for(html, "solicitor_id"))
        self.assertIn('value="2" selected', self._select_for(html, "tranche"))

    def test_solicitation_apply_filter_uses_selected_values(self):
        response = self.client.get(f"/solicitations?solicitor_id={self.solicitor_b_id}&tranche=3")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Gamma Ready", html)
        self.assertNotIn("Alpha Ready", html)
        self.assertNotIn("Beta Incomplete", html)
        self.assertNotIn("Delta Incomplete", html)

    def test_solicitation_clear_filter_clears_persisted_values(self):
        self.client.get(f"/solicitations?solicitor_id={self.solicitor_b_id}&tranche=2")

        response = self.client.get("/solicitations/clear-filter", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        for partner_name in ("Alpha Ready", "Beta Incomplete", "Delta Incomplete", "Gamma Ready"):
            self.assertIn(partner_name, html)
        self.assertIn('value="" selected', self._select_for(html, "solicitor_id"))
        self.assertIn('value="" selected', self._select_for(html, "tranche"))

    def test_solicitation_filters_persist_selected_values(self):
        first_response = self.client.get(f"/solicitations?solicitor_id={self.solicitor_b_id}&tranche=2")
        self.assertEqual(first_response.status_code, 200)

        response = self.client.get("/solicitations")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Delta Incomplete", html)
        self.assertNotIn("Alpha Ready", html)
        self.assertNotIn("Beta Incomplete", html)
        self.assertNotIn("Gamma Ready", html)
        self.assertIn(f'value="{self.solicitor_b_id}" selected', self._select_for(html, "solicitor_id"))
        self.assertIn('value="2" selected', self._select_for(html, "tranche"))

    def test_invalid_solicitation_tranche_filter_is_ignored_for_current_request(self):
        self.client.get("/solicitations?tranche=2")

        response = self.client.get("/solicitations?tranche=999")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        for partner_name in ("Alpha Ready", "Beta Incomplete", "Delta Incomplete", "Gamma Ready"):
            self.assertIn(partner_name, html)
        self.assertIn('value="" selected', self._select_for(html, "tranche"))

    def _set_workflow_statuses(self):
        with self.app.app_context():
            statuses = {
                "Alpha Ready": "not_contacted",
                "Beta Incomplete": "contacted",
                "Delta Incomplete": "responded",
                "Gamma Ready": "donated",
            }
            for partner_name, status in statuses.items():
                solicitation = db.session.get(Solicitation, self.ids_by_partner[partner_name])
                solicitation.status = status
            db.session.commit()

    def test_status_filter_shows_only_canonical_not_contacted_and_active_control(self):
        self._set_workflow_statuses()

        response = self.client.get("/solicitations?status=not_contacted")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Alpha Ready", html)
        for name in ("Beta Incomplete", "Delta Incomplete", "Gamma Ready"):
            self.assertNotIn(name, html)
        self.assertIn('value="not_contacted" selected', self._select_for(html, "status"))
        self.assertIn("Workflow Status", html)
        self.assertIn("Not Contacted", self._row_for_partner(html, "Alpha Ready"))
        self.assertIn(f'/solicitations/{self.alpha_ready_id}"', html)
        self.assertIn(f'/solicitations/{self.alpha_ready_id}/edit"', html)

    def test_legacy_status_query_is_normalized(self):
        self._set_workflow_statuses()

        response = self.client.get("/solicitations?status=donated")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Gamma Ready", html)
        for name in ("Alpha Ready", "Beta Incomplete", "Delta Incomplete"):
            self.assertNotIn(name, html)
        self.assertIn('value="gift_received" selected', self._select_for(html, "status"))

    def test_invalid_status_filter_is_safely_ignored(self):
        self._set_workflow_statuses()

        response = self.client.get("/solicitations?status=unknown")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        for name in self.ids_by_partner:
            self.assertIn(name, html)
        self.assertIn('value="" selected', self._select_for(html, "status"))

    def test_status_combines_with_solicitor_and_tranche_filters(self):
        self._set_workflow_statuses()
        with self.app.app_context():
            delta = db.session.get(Solicitation, self.ids_by_partner["Delta Incomplete"])
            delta.status = "not_contacted"
            db.session.commit()

        response = self.client.get(
            f"/solicitations?status=not_contacted&solicitor_id={self.solicitor_b_id}&tranche=2"
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Delta Incomplete", html)
        for name in ("Alpha Ready", "Beta Incomplete", "Gamma Ready"):
            self.assertNotIn(name, html)
        self.assertIn('value="not_contacted" selected', self._select_for(html, "status"))
        self.assertIn(
            f'value="{self.solicitor_b_id}" selected', self._select_for(html, "solicitor_id")
        )
        self.assertIn('value="2" selected', self._select_for(html, "tranche"))

    def test_status_combines_independently_with_existing_filters(self):
        self._set_workflow_statuses()
        with self.app.app_context():
            beta = db.session.get(Solicitation, self.ids_by_partner["Beta Incomplete"])
            beta.status = "not_contacted"
            db.session.commit()

        by_solicitor = self.client.get(
            f"/solicitations?status=not_contacted&solicitor_id={self.solicitor_a_id}"
        ).get_data(as_text=True)
        self.assertIn("Alpha Ready", by_solicitor)
        self.assertIn("Beta Incomplete", by_solicitor)
        self.assertNotIn("Delta Incomplete", by_solicitor)

        by_tranche = self.client.get(
            "/solicitations/clear-filter", follow_redirects=True
        )
        self.assertEqual(by_tranche.status_code, 200)
        by_tranche = self.client.get(
            "/solicitations?status=not_contacted&tranche=2"
        ).get_data(as_text=True)
        self.assertIn("Beta Incomplete", by_tranche)
        self.assertNotIn("Alpha Ready", by_tranche)
        self.assertNotIn("Delta Incomplete", by_tranche)

    def test_status_filter_can_be_cleared_without_resetting_other_filters(self):
        self._set_workflow_statuses()
        self.client.get(
            f"/solicitations?status=not_contacted&solicitor_id={self.solicitor_a_id}"
        )

        response = self.client.get("/solicitations?status=")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Alpha Ready", html)
        self.assertIn("Beta Incomplete", html)
        self.assertIn('value="" selected', self._select_for(html, "status"))
        self.assertIn(
            f'value="{self.solicitor_a_id}" selected', self._select_for(html, "solicitor_id")
        )
        self.assertIn('value="" selected', self._select_for(html, "tranche"))

    def test_status_filter_zero_results_renders_empty_state(self):
        self._set_workflow_statuses()

        response = self.client.get(
            f"/solicitations?status=declined&solicitor_id={self.solicitor_a_id}&tranche=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "No solicitations match the selected filters.", response.get_data(as_text=True)
        )

    def test_complete_filter_uses_existing_readiness_rule_and_keeps_actions(self):
        response = self.client.get("/solicitations?complete=true&status=")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Alpha Ready", html)
        self.assertIn("Delta Incomplete", html)
        self.assertNotIn("Beta Incomplete", html)
        self.assertNotIn("Gamma Ready", html)
        self.assertIn('value="true" selected', self._select_for(html, "complete"))
        for name in ("Alpha Ready", "Delta Incomplete"):
            solicitation_id = self.ids_by_partner[name]
            row = self._row_for_partner(html, name)
            self.assertIn(f'/solicitations/{solicitation_id}"', row)
            self.assertIn(f'/solicitations/{solicitation_id}/edit"', row)

    def test_complete_filter_combines_with_existing_filters(self):
        self._set_workflow_statuses()
        response = self.client.get(
            f"/solicitations?complete=true&status=pledged&solicitor_id={self.solicitor_b_id}&tranche=2"
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Delta Incomplete", html)
        for name in ("Alpha Ready", "Beta Incomplete", "Gamma Ready"):
            self.assertNotIn(name, html)
        self.assertIn('value="true" selected', self._select_for(html, "complete"))
        self.assertIn('value="pledged" selected', self._select_for(html, "status"))

    def test_invalid_complete_filter_is_ignored_and_empty_state_renders(self):
        invalid_response = self.client.get("/solicitations?complete=invalid&status=")
        self.assertEqual(invalid_response.status_code, 200)
        invalid_html = invalid_response.get_data(as_text=True)
        for name in self.ids_by_partner:
            self.assertIn(name, invalid_html)
        self.assertIn('value="" selected', self._select_for(invalid_html, "complete"))

        empty_response = self.client.get(
            f"/solicitations?complete=true&status=declined&solicitor_id={self.solicitor_a_id}&tranche=3"
        )
        self.assertEqual(empty_response.status_code, 200)
        self.assertIn(
            "No solicitations match the selected filters.",
            empty_response.get_data(as_text=True),
        )

    def test_solicitation_create_records_pledged_amount(self):
        response = self.client.post(
            "/solicitations/new",
            data={
                "campaign_id": str(self.campaign_id),
                "partner_id": str(self.epsilon_new_partner_id),
                "solicitor_person_id": str(self.solicitor_a_id),
                "mrpoc_person_id": str(self.mrpoc_a_id),
                "tranche": "2",
                "business_volume": "1800",
                "amount_requested": "500",
                "amount_pledged": "325.50",
                "amount_received": "0",
                "status": "contacted",
                "notes": "Pledge captured",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            created = db.session.query(Solicitation).filter_by(partner_id=self.epsilon_new_partner_id).one()
            self.assertEqual(created.amount_requested, Decimal("500.00"))
            self.assertEqual(created.amount_pledged, Decimal("325.50"))

    def test_solicitation_edit_updates_pledged_amount(self):
        response = self.client.post(
            f"/solicitations/{self.alpha_ready_id}/edit",
            data={
                "campaign_id": str(self.campaign_id),
                "partner_id": str(self.alpha_ready_partner_id),
                "solicitor_person_id": str(self.solicitor_a_id),
                "mrpoc_person_id": str(self.mrpoc_a_id),
                "tranche": "1",
                "business_volume": "5100",
                "amount_requested": "2500.00",
                "amount_pledged": "825.00",
                "amount_received": "125.00",
                "status": "pledged",
                "notes": "Updated pledge",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            updated = db.session.get(Solicitation, self.alpha_ready_id)
            self.assertEqual(updated.amount_requested, Decimal("2500.00"))
            self.assertEqual(updated.amount_pledged, Decimal("825.00"))

    def test_solicitation_create_renders_requested_amount_dropdown(self):
        response = self.client.get("/solicitations/new")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        select_html = self._requested_amount_select(html)

        self.assertNotIn('type="text" class="form-control" id="amount_requested"', html)
        self.assertIn('name="amount_requested"', select_html)
        self.assertIn('value="" selected', select_html)
        for value, label in (
            ("500.00", "$500"),
            ("1000.00", "$1,000"),
            ("2500.00", "$2,500"),
            ("5000.00", "$5,000"),
            ("10000.00", "$10,000"),
        ):
            self.assertIn(f'value="{value}"', select_html)
            self.assertIn(label, select_html)

    def test_solicitation_edit_preserves_selected_requested_amount(self):
        response = self.client.get(f"/solicitations/{self.alpha_ready_id}/edit")
        self.assertEqual(response.status_code, 200)
        select_html = self._requested_amount_select(response.get_data(as_text=True))

        self.assertIn('value="1000.00" selected', select_html)
        self.assertIn("$1,000", select_html)

    def test_solicitation_create_rejects_invalid_requested_amount(self):
        response = self.client.post(
            "/solicitations/new",
            data={
                "campaign_id": str(self.campaign_id),
                "partner_id": str(self.epsilon_new_partner_id),
                "solicitor_person_id": str(self.solicitor_a_id),
                "mrpoc_person_id": str(self.mrpoc_a_id),
                "tranche": "2",
                "business_volume": "1800",
                "amount_requested": "750",
                "amount_pledged": "325.50",
                "amount_received": "0",
                "status": "contacted",
                "notes": "Invalid request",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Please select a permitted requested amount.", html)

        with self.app.app_context():
            created = db.session.query(Solicitation).filter_by(partner_id=self.epsilon_new_partner_id).one_or_none()
            self.assertIsNone(created)

    def test_solicitation_detail_displays_requested_pledged_received(self):
        response = self.client.get(f"/solicitations/{self.alpha_ready_id}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Requested Amount", html)
        self.assertIn("Pledged Amount", html)
        self.assertIn("Received Amount", html)
        self.assertTrue(html.find("Requested Amount") < html.find("Pledged Amount") < html.find("Received Amount"))
        self.assertIn("$750.00", html)


if __name__ == "__main__":
    unittest.main()
