import subprocess
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Campaign, Partner, Person, Solicitation, User
from app.reports.registry import (
    build_campaign_by_partner_context,
    build_campaign_by_participation_context,
    get_report,
    list_reports,
)
from app.reports.report_service import report_pdf_path


class ReportsTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_reports_"))
        self._reports_dir = self._tmp_dir / "generated_reports"

        class TestConfig(Config):
            SECRET_KEY = "test-secret"
            TESTING = True
            DATABASE_URL = f"sqlite:///{self._tmp_dir / 'test.db'}"
            GENERATED_REPORTS_DIR = str(self._reports_dir)

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            user = User(
                username="reader",
                email="reader@example.com",
                role=User.ROLE_READER,
                is_active=True,
            )
            user.set_password("password123")
            db.session.add(user)

            solicitor = Person(
                first_name="Alex",
                last_name="Assigned",
                email="alex.assigned@example.com",
                phone="410-555-0100",
            )
            partner = Partner(
                partner_name="Alpha Partner",
                display_name="Alpha Display",
                partner_type="Finance",
            )
            campaign_2026 = Campaign(
                campaign_year=2026,
                campaign_name="2026 Scholarship Campaign",
                status="active",
            )
            campaign_2025 = Campaign(
                campaign_year=2025,
                campaign_name="2025 Scholarship Campaign",
                status="closed",
            )
            db.session.add_all([solicitor, partner, campaign_2026, campaign_2025])
            db.session.flush()

            solicitation = Solicitation(
                partner_id=partner.id,
                campaign_id=campaign_2026.id,
                solicitor_person_id=solicitor.id,
                tranche=1,
                business_volume=Decimal("0"),
                amount_requested=Decimal("1000"),
                amount_pledged=Decimal("750"),
                amount_received=Decimal("500"),
                status="donated",
            )
            db.session.add(solicitation)
            db.session.commit()

            self.user_id = str(user.id)
            self.campaign_2026_id = campaign_2026.id
            self.campaign_2025_id = campaign_2025.id

        with self.client.session_transaction() as session:
            session["_user_id"] = self.user_id
            session["_fresh"] = True

    def _fake_xelatex(self, command, **kwargs):
        output_dir = Path(command[command.index("-output-directory") + 1])
        tex_path = Path(command[-1])
        pdf_path = output_dir / tex_path.with_suffix(".pdf").name
        pdf_path.write_bytes(b"%PDF-report")
        self.rendered_tex = tex_path.read_text(encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def test_report_registry_contains_both_campaign_reports(self):
        reports = list_reports()

        self.assertEqual(
            [report.id for report in reports],
            ["campaign-by-participation", "campaign-by-partner"],
        )
        report = get_report("campaign-by-partner")
        self.assertIsNotNone(report)
        self.assertEqual(report.label, "Campaign by Partner")
        self.assertEqual(report.template_name, "campaign_by_partner.tex.j2")
        participation_report = get_report("campaign-by-participation")
        self.assertIsNotNone(participation_report)
        self.assertEqual(participation_report.label, "Campaign by Participation")
        self.assertEqual(
            participation_report.template_name,
            "campaign_by_participation.tex.j2",
        )

    def test_reports_page_shows_campaign_selector_and_report_cards(self):
        response = self.client.get("/reports")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Campaign:", html)
        self.assertIn("2026 Scholarship Campaign", html)
        self.assertIn("Generate Reports", html)
        self.assertIn("Available Reports", html)
        self.assertEqual(html.count("Campaign by Partner"), 2)
        self.assertEqual(html.count("Campaign by Participation"), 2)
        self.assertIn("Generate", html)
        self.assertIn("View PDF", html)
        self.assertIn("No PDF generated for this campaign yet.", html)

    def test_reports_menu_links_to_reports_page(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('href="/reports"', html)
        self.assertIn(">Reports</a>", html)

    def test_campaign_selection_is_persisted_in_session(self):
        response = self.client.get(f"/reports?campaign_id={self.campaign_2025_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="{}" selected'.format(self.campaign_2025_id), response.get_data(as_text=True))

        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="{}" selected'.format(self.campaign_2025_id), response.get_data(as_text=True))

    def test_report_generation_creates_pdf_and_makes_report_available(self):
        with patch("app.reports.report_service.subprocess.run", side_effect=self._fake_xelatex) as run:
            response = self.client.post(
                "/reports/campaign-by-partner/generate",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(run.call_count, 2)
        html = response.get_data(as_text=True)
        self.assertIn("Generated campaign_by_partner_2026.pdf.", html)
        self.assertIn("campaign_by_partner_2026.pdf", html)
        self.assertIn('href="/reports/campaign-by-partner/pdf"', html)

        with self.app.app_context():
            report = get_report("campaign-by-partner")
            campaign = db.session.get(Campaign, self.campaign_2026_id)
            self.assertTrue(report_pdf_path(report, campaign).is_file())

    def test_participation_report_generation_creates_separate_pdf_with_totals(self):
        with patch(
            "app.reports.report_service.subprocess.run",
            side_effect=self._fake_xelatex,
        ) as run:
            response = self.client.post(
                "/reports/campaign-by-participation/generate",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(run.call_count, 2)
        html = response.get_data(as_text=True)
        self.assertIn("Generated campaign_by_participation_2026.pdf.", html)
        self.assertIn('href="/reports/campaign-by-participation/pdf"', html)
        self.assertIn(r"\textbf{Totals}", self.rendered_tex)
        self.assertIn(r"\$1,000", self.rendered_tex)
        self.assertIn(r"\$750", self.rendered_tex)
        self.assertIn(r"\$500", self.rendered_tex)

        with self.app.app_context():
            participation = get_report("campaign-by-participation")
            partner = get_report("campaign-by-partner")
            campaign = db.session.get(Campaign, self.campaign_2026_id)
            participation_path = report_pdf_path(participation, campaign)
            partner_path = report_pdf_path(partner, campaign)
            self.assertTrue(participation_path.is_file())
            self.assertNotEqual(participation_path, partner_path)

    def test_campaign_contexts_share_totals_but_apply_different_ordering(self):
        with self.app.app_context():
            campaign = db.session.get(Campaign, self.campaign_2026_id)
            solicitor = db.session.scalar(db.select(Person))
            for name, received in (("Zulu Display", "500"), ("Beta Display", "900")):
                partner = Partner(partner_name=name, display_name=name, partner_type="Other")
                db.session.add(partner)
                db.session.flush()
                db.session.add(
                    Solicitation(
                        partner_id=partner.id,
                        campaign_id=campaign.id,
                        solicitor_person_id=solicitor.id,
                        amount_requested=Decimal("100"),
                        amount_pledged=Decimal("100"),
                        amount_received=Decimal(received),
                        status="donated",
                    )
                )
            db.session.commit()

            partner_context = build_campaign_by_partner_context(campaign)
            participation_context = build_campaign_by_participation_context(campaign)

        self.assertEqual(
            [row.partner_display_name for row in partner_context["rows"]],
            ["Alpha Display", "Beta Display", "Zulu Display"],
        )
        self.assertEqual(
            [row.partner_display_name for row in participation_context["rows"]],
            ["Beta Display", "Alpha Display", "Zulu Display"],
        )
        for total_name in ("total_requested", "total_pledged", "total_contributed"):
            self.assertEqual(partner_context[total_name], participation_context[total_name])
        self.assertEqual(participation_context["total_contributed"], Decimal("1900"))

    def test_report_pdf_route_serves_generated_pdf(self):
        with self.app.app_context():
            report = get_report("campaign-by-partner")
            campaign = db.session.get(Campaign, self.campaign_2026_id)
            output_path = report_pdf_path(report, campaign)
            output_path.write_bytes(b"%PDF-existing")

        response = self.client.get("/reports/campaign-by-partner/pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertEqual(response.data, b"%PDF-existing")


if __name__ == "__main__":
    unittest.main()
