import tempfile
import unittest
from datetime import UTC, datetime
from os import utime
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Campaign, Contact, Partner, Person, Solicitation, User


class LettersQueueTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="sb_letters_queue_"))
        self._generated_dir = self._tmp_dir / "generated_letters"

        class TestConfig(Config):
            SECRET_KEY = "test-secret"
            TESTING = True
            DATABASE_URL = f"sqlite:///{self._tmp_dir / 'test.db'}"
            GENERATED_LETTERS_DIR = str(self._generated_dir)

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
                last_name="Adams",
                email="alex.adams@example.com",
                phone="4105551212",
            )
            solicitor_b = Person(
                first_name="Blair",
                last_name="Baker",
                email="blair.baker@example.com",
                phone="410.555.1213",
            )
            mrpoc_a = Person(
                first_name="Morgan",
                last_name="Reed",
                email="morgan.reed@example.com",
                phone="(410) 555-1214",
            )
            mrpoc_b = Person(
                first_name="Casey",
                last_name="Shaw",
                email="casey.shaw@example.com",
                phone="410-555-1215",
            )
            db.session.add_all([solicitor_a, solicitor_b, mrpoc_a, mrpoc_b])

            campaign = Campaign(
                campaign_year=2026,
                campaign_name="2026 Scholarship Campaign",
                status="active",
            )
            db.session.add(campaign)
            db.session.flush()

            partner_ready = Partner(
                partner_name="Zulu Partner",
                display_name="Alpha Display",
                partner_type="Finance",
                address_1="123 Main Street",
                address_2="Suite 400",
                city="Baltimore",
                state="MD",
                postal_code="21201",
            )
            partner_incomplete = Partner(
                partner_name="Bravo Partner",
                partner_type=None,
                address_1="22 Incomplete Road",
                city="Towson",
                state="MD",
                postal_code="21204",
            )
            partner_incomplete_2 = Partner(
                partner_name="Delta Partner",
                partner_type=None,
                address_1="33 Pending Avenue",
                city="Lutherville",
                state="MD",
                postal_code="21093",
            )
            partner_ready_no_display = Partner(
                partner_name="Beta Partner",
                display_name=None,
                partner_type="Insurance",
                address_1="456 Oak Lane",
                city="Towson",
                state="MD",
                postal_code="21286",
            )
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
                mrpoc_person_id=mrpoc_a.id,
                business_volume=5000,
                amount_requested=1250,
            )
            solicitation_incomplete = Solicitation(
                partner_id=partner_incomplete.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_a.id,
                mrpoc_person_id=mrpoc_a.id,
                business_volume=4000,
                amount_requested=1000,
            )
            solicitation_ready_2 = Solicitation(
                partner_id=partner_ready_no_display.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_b.id,
                mrpoc_person_id=mrpoc_b.id,
                business_volume=2200,
                amount_requested=700,
            )
            solicitation_incomplete_2 = Solicitation(
                partner_id=partner_incomplete_2.id,
                campaign_id=campaign.id,
                solicitor_person_id=solicitor_b.id,
                mrpoc_person_id=mrpoc_b.id,
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
            db.session.flush()

            db.session.add_all(
                [
                    Contact(
                        partner_id=partner_ready.id,
                        first_name="John",
                        last_name="Smith",
                        title="Manager",
                        is_primary=True,
                    ),
                    Contact(
                        partner_id=partner_ready_no_display.id,
                        first_name="Jane",
                        last_name="Jones",
                        title="Director",
                        is_primary=True,
                    ),
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

    def _row_for_partner(self, html: str, partner_name: str) -> str:
        marker = html.find(partner_name)
        self.assertNotEqual(marker, -1, msg=f"Missing row for partner: {partner_name}")
        row_start = html.rfind("<tr", 0, marker)
        self.assertNotEqual(row_start, -1, msg=f"Missing row start for partner: {partner_name}")
        row_end = html.find("</tr>", marker)
        self.assertNotEqual(row_end, -1, msg=f"Missing row end for partner: {partner_name}")
        return html[row_start : row_end + len("</tr>")]

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

    def test_letter_generation_is_blocked_when_required_contact_data_is_missing(self):
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.ready_id)
            self.assertIsNotNone(solicitation)
            self.assertIsNotNone(solicitation.solicitor)
            solicitation.solicitor.email = None
            db.session.commit()

        response = self.client.get(
            f"/letters/solicitation.pdf?solicitation_id={self.ready_id}",
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

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/letters?solicitor_id={self.solicitor_a_id}", response.headers["Location"])
        response.close()

    def test_contacted_solicitation_shows_archived_letter_action(self):
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.ready_id)
            solicitation.status = "contacted"
            db.session.commit()

        response = self.client.get("/letters")
        self.assertEqual(response.status_code, 200)
        row = self._row_for_partner(response.get_data(as_text=True), "Alpha Display")

        self.assertIn("Letter Archived", row)
        self.assertNotIn(
            f"/letters/solicitation.pdf?solicitation_id={self.ready_id}",
            row,
        )

    def test_contacted_solicitation_cannot_regenerate_letter(self):
        output_path = self._generated_dir / f"solicitation_{self.ready_id}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-archived")
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.ready_id)
            solicitation.status = "contacted"
            db.session.commit()

        with patch("app.main.routes.generate_solicitation_pdf_bytes", return_value=b"%PDF-new") as generate_pdf:
            response = self.client.get(
                f"/letters/solicitation.pdf?solicitation_id={self.ready_id}",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Solicitation letter is archived and cannot be regenerated.",
            response.get_data(as_text=True),
        )
        generate_pdf.assert_not_called()
        self.assertEqual(output_path.read_bytes(), b"%PDF-archived")
        response.close()

    def test_generated_pdf_remains_accessible_after_contacted(self):
        output_path = self._generated_dir / f"solicitation_{self.ready_id}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-archived-view")
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.ready_id)
            solicitation.status = "contacted"
            db.session.commit()

        response = self.client.get(
            f"/letters/generated/solicitation/{self.ready_id}.pdf"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertEqual(response.data, b"%PDF-archived-view")
        response.close()

    def test_partner_and_contact_edits_do_not_change_archived_letter(self):
        output_path = self._generated_dir / f"solicitation_{self.ready_id}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-original-archived")
        with self.app.app_context():
            solicitation = db.session.get(Solicitation, self.ready_id)
            solicitation.status = "contacted"
            solicitation.partner.display_name = "Updated Display"
            primary_contact = db.session.query(Contact).filter_by(
                partner_id=solicitation.partner_id,
                is_primary=True,
            ).one()
            primary_contact.last_name = "Updated"
            db.session.commit()

        with patch("app.main.routes.generate_solicitation_pdf_bytes", return_value=b"%PDF-rebuilt") as generate_pdf:
            response = self.client.get(
                f"/letters/solicitation.pdf?solicitation_id={self.ready_id}",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        generate_pdf.assert_not_called()
        self.assertEqual(output_path.read_bytes(), b"%PDF-original-archived")
        response.close()

    def test_letter_generation_saves_pdf_to_filesystem(self):
        with patch("app.main.routes.generate_solicitation_pdf_bytes", return_value=b"%PDF-save"):
            response = self.client.get(
                f"/letters/solicitation.pdf?solicitation_id={self.ready_id}"
            )

        self.assertEqual(response.status_code, 302)
        output_path = self._generated_dir / f"solicitation_{self.ready_id}.pdf"
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.read_bytes(), b"%PDF-save")
        response.close()

    def test_letter_regeneration_replaces_existing_file_without_duplicates(self):
        with patch("app.main.routes.generate_solicitation_pdf_bytes", return_value=b"%PDF-v1"):
            first_response = self.client.get(
                f"/letters/solicitation.pdf?solicitation_id={self.ready_id}"
            )
            first_response.close()

        with patch("app.main.routes.generate_solicitation_pdf_bytes", return_value=b"%PDF-v2"):
            second_response = self.client.get(
                f"/letters/solicitation.pdf?solicitation_id={self.ready_id}"
            )
            second_response.close()

        files = sorted(self._generated_dir.glob("solicitation_*.pdf"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, f"solicitation_{self.ready_id}.pdf")
        self.assertEqual(files[0].read_bytes(), b"%PDF-v2")

    def test_generated_letters_listing_shows_saved_pdf(self):
        with patch("app.main.routes.generate_solicitation_pdf_bytes", return_value=b"%PDF-list"):
            generation_response = self.client.get(
                f"/letters/solicitation.pdf?solicitation_id={self.ready_id}",
                follow_redirects=True,
            )
        self.assertEqual(generation_response.status_code, 200)
        self.assertIn(
            f"Generated solicitation_{self.ready_id}.pdf.",
            generation_response.get_data(as_text=True),
        )
        generation_response.close()

        response = self.client.get("/letters")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Generated Solicitation Letters", html)
        self.assertIn(f"solicitation_{self.ready_id}.pdf", html)
        self.assertIn("Alpha Display", html)
        self.assertIn(
            f"/letters/generated/solicitation/{self.ready_id}.pdf",
            html,
        )

    def test_generated_letter_timestamp_is_displayed_in_eastern_time(self):
        output_path = self._generated_dir / f"solicitation_{self.ready_id}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-time")
        generated_at = datetime(2026, 7, 23, 18, 15, tzinfo=UTC)
        utime(output_path, (generated_at.timestamp(), generated_at.timestamp()))

        response = self.client.get("/letters")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "2026-07-23 02:15:00 PM EDT",
            response.get_data(as_text=True),
        )
        response.close()

    def test_generated_letter_view_endpoint_serves_saved_pdf(self):
        output_path = self._generated_dir / f"solicitation_{self.ready_id}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-view")

        response = self.client.get(
            f"/letters/generated/solicitation/{self.ready_id}.pdf"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertEqual(response.data, b"%PDF-view")
        response.close()

    def test_solicitor_filter_applies_to_generated_letters_section(self):
        first_path = self._generated_dir / f"solicitation_{self.ready_id}.pdf"
        second_path = self._generated_dir / f"solicitation_{self.ready_2_id}.pdf"
        first_path.parent.mkdir(parents=True, exist_ok=True)
        first_path.write_bytes(b"%PDF-a")
        second_path.write_bytes(b"%PDF-b")

        filtered_a = self.client.get(f"/letters?solicitor_id={self.solicitor_a_id}")
        html_a = filtered_a.get_data(as_text=True)
        self.assertIn(f"solicitation_{self.ready_id}.pdf", html_a)
        self.assertNotIn(f"solicitation_{self.ready_2_id}.pdf", html_a)
        filtered_a.close()

        filtered_b = self.client.get(f"/letters?solicitor_id={self.solicitor_b_id}")
        html_b = filtered_b.get_data(as_text=True)
        self.assertIn(f"solicitation_{self.ready_2_id}.pdf", html_b)
        self.assertNotIn(f"solicitation_{self.ready_id}.pdf", html_b)
        filtered_b.close()

    def test_generation_redirect_preserves_selected_solicitor_filter(self):
        with patch("app.main.routes.generate_solicitation_pdf_bytes", return_value=b"%PDF-filter"):
            response = self.client.get(
                f"/letters/solicitation.pdf?solicitation_id={self.ready_id}&solicitor_id={self.solicitor_a_id}",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn(f"Generated solicitation_{self.ready_id}.pdf.", html)
        self.assertIn(f"solicitor_id={self.solicitor_a_id}", html)
        self.assertIn(f"solicitation_{self.ready_id}.pdf", html)
        response.close()

    def test_unfiltered_generated_letters_view_shows_all_letters(self):
        first_path = self._generated_dir / f"solicitation_{self.ready_id}.pdf"
        second_path = self._generated_dir / f"solicitation_{self.ready_2_id}.pdf"
        first_path.parent.mkdir(parents=True, exist_ok=True)
        first_path.write_bytes(b"%PDF-a")
        second_path.write_bytes(b"%PDF-b")

        response = self.client.get("/letters")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn(f"solicitation_{self.ready_id}.pdf", html)
        self.assertIn(f"solicitation_{self.ready_2_id}.pdf", html)
        response.close()

    def test_mailing_list_generation_includes_only_ready_solicitations(self):
        response = self.client.post("/letters/mailing-list", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Generated mailing list mailing_list_", html)

        files = sorted((self._generated_dir / "mailing_lists").glob("mailing_list_*.txt"))
        self.assertEqual(len(files), 1)
        content = files[0].read_text(encoding="utf-8")
        self.assertIn("Zulu Partner", content)
        self.assertIn("Beta Partner", content)
        self.assertNotIn("Bravo Partner", content)
        self.assertNotIn("Delta Partner", content)
        response.close()

    def test_mailing_list_generation_respects_solicitor_filter(self):
        response = self.client.post(
            "/letters/mailing-list",
            data={"solicitor_id": self.solicitor_b_id},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        files = sorted((self._generated_dir / "mailing_lists").glob("mailing_list_*.txt"))
        self.assertEqual(len(files), 1)
        content = files[0].read_text(encoding="utf-8")
        self.assertIn("Beta Partner", content)
        self.assertNotIn("Zulu Partner", content)
        self.assertNotIn("Bravo Partner", content)
        response.close()

    def test_mailing_list_address_formatting(self):
        response = self.client.post("/letters/mailing-list", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        files = sorted((self._generated_dir / "mailing_lists").glob("mailing_list_*.txt"))
        content = files[0].read_text(encoding="utf-8")
        expected = (
            "John Smith\n"
            "Zulu Partner\n"
            "123 Main Street\n"
            "Suite 400\n"
            "Baltimore, MD 21201\n\n"
            "Jane Jones\n"
            "Beta Partner\n"
            "456 Oak Lane\n"
            "Towson, MD 21286"
        )
        self.assertEqual(content, expected)
        response.close()

    def test_generated_mailing_list_listing_is_displayed(self):
        generation = self.client.post("/letters/mailing-list", follow_redirects=True)
        self.assertEqual(generation.status_code, 200)
        generation.close()

        response = self.client.get("/letters")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Generated Mailing Lists", html)
        self.assertIn("mailing_list_", html)
        self.assertIn("/letters/generated/mailing-lists/", html)
        response.close()

    def test_generated_mailing_list_view_and_download(self):
        generation = self.client.post("/letters/mailing-list", follow_redirects=True)
        self.assertEqual(generation.status_code, 200)
        generation.close()

        files = sorted((self._generated_dir / "mailing_lists").glob("mailing_list_*.txt"))
        self.assertEqual(len(files), 1)
        filename = files[0].name

        view_response = self.client.get(f"/letters/generated/mailing-lists/{filename}")
        self.assertEqual(view_response.status_code, 200)
        self.assertEqual(view_response.mimetype, "text/plain")
        self.assertIn("Zulu Partner", view_response.get_data(as_text=True))
        view_response.close()

        download_response = self.client.get(
            f"/letters/generated/mailing-lists/{filename}/download"
        )
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.mimetype, "text/plain")
        disposition = download_response.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)
        self.assertIn(filename, disposition)
        download_response.close()

    def test_generated_mailing_list_delete_success(self):
        generation = self.client.post("/letters/mailing-list", follow_redirects=True)
        self.assertEqual(generation.status_code, 200)
        generation.close()

        files = sorted((self._generated_dir / "mailing_lists").glob("mailing_list_*.txt"))
        self.assertEqual(len(files), 1)
        filename = files[0].name

        delete_response = self.client.post(
            f"/letters/generated/mailing-lists/{filename}/delete",
            follow_redirects=True,
        )
        self.assertEqual(delete_response.status_code, 200)
        html = delete_response.get_data(as_text=True)
        self.assertIn(f"Deleted mailing list {filename}.", html)
        self.assertFalse((self._generated_dir / "mailing_lists" / filename).exists())
        delete_response.close()

    def test_generated_mailing_list_delete_missing_file(self):
        missing_name = "mailing_list_20260610_120000_000000.txt"
        delete_response = self.client.post(
            f"/letters/generated/mailing-lists/{missing_name}/delete",
            follow_redirects=True,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertIn(
            "Generated mailing list not found.",
            delete_response.get_data(as_text=True),
        )
        delete_response.close()

    def test_generated_mailing_list_delete_rejects_invalid_filename(self):
        mailing_list_dir = self._generated_dir / "mailing_lists"
        mailing_list_dir.mkdir(parents=True, exist_ok=True)
        protected = mailing_list_dir / "notes.txt"
        protected.write_text("do not delete", encoding="utf-8")

        delete_response = self.client.post(
            "/letters/generated/mailing-lists/notes.txt/delete",
            follow_redirects=True,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertIn(
            "Generated mailing list not found.",
            delete_response.get_data(as_text=True),
        )
        self.assertTrue(protected.exists())
        delete_response.close()

    def test_generated_mailing_list_delete_redirect_behavior(self):
        generation = self.client.post("/letters/mailing-list", follow_redirects=True)
        self.assertEqual(generation.status_code, 200)
        generation.close()

        files = sorted((self._generated_dir / "mailing_lists").glob("mailing_list_*.txt"))
        filename = files[0].name

        delete_response = self.client.post(
            f"/letters/generated/mailing-lists/{filename}/delete",
            follow_redirects=False,
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertIn("/letters", delete_response.headers.get("Location", ""))
        delete_response.close()


if __name__ == "__main__":
    unittest.main()
