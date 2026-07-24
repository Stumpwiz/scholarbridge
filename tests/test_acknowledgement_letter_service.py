import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

from app import create_app
from app.config import Config
from app.extensions import db
from app.main.letter_service import (
    acknowledgement_letter_date,
    build_acknowledgement_letter_context_for_solicitation,
)
from app.models import Campaign, Contact, Partner, Person, Solicitation
from app.services.docx_template_service import DocxTemplateService
from app.services.letters.acknowledgement import build_acknowledgement_render_plan


class AcknowledgementLetterServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="sb_ack_service_"))

        class TestConfig(Config):
            TESTING = True
            SECRET_KEY = "test-secret"
            DATABASE_URL = f"sqlite:///{self.temp_dir / 'test.db'}"

        self.app = create_app(TestConfig)
        self.project_root = Path(self.app.root_path).parent
        self.template_path = (
            self.project_root / "docs/private/letter_templates/acknowledgement.docx"
        )
        self.signature_path = self.project_root / "docs/private/img/ellenBreshSig.jpg"
        with self.app.app_context():
            db.create_all()
            campaign = Campaign(campaign_year=2026, campaign_name="Campaign", status="active")
            partner = Partner(
                partner_name="Original Company",
                partner_type="Finance",
                address_1="100 Original Road",
                address_2="Suite 5",
                city="Baltimore",
                state="MD",
                postal_code="21201",
            )
            mrpoc = Person(first_name="Morgan", last_name="Reed")
            db.session.add_all([campaign, partner, mrpoc])
            db.session.flush()
            contact = Contact(
                partner_id=partner.id,
                title="Ms.",
                first_name="Current",
                last_name="Contact",
                is_primary=True,
            )
            solicitation = Solicitation(
                partner_id=partner.id,
                campaign_id=campaign.id,
                mrpoc_person_id=mrpoc.id,
                amount_received=Decimal("1250.50"),
                status="donated",
            )
            db.session.add_all([contact, solicitation])
            db.session.commit()
            self.solicitation_id = solicitation.id

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _context(self):
        with self.app.app_context():
            return build_acknowledgement_letter_context_for_solicitation(
                self.solicitation_id,
                now=datetime(2026, 7, 27, 3, 30, tzinfo=UTC),
            )

    def test_context_uses_current_contact_amount_and_eastern_date(self):
        with self.app.app_context():
            contact = db.session.query(Contact).one()
            contact.first_name = "Updated"
            contact.last_name = "Recipient"
            contact.partner.address_1 = "900 Current Avenue"
            db.session.commit()

        context = self._context()
        self.assertEqual(context["letter_date"], "July 26, 2026")
        self.assertEqual(context["recipient_line"], "Ms. Updated Recipient")
        self.assertEqual(context["address_1"], "900 Current Avenue")
        self.assertEqual(context["amount_received"], "$1,250.50")
        self.assertEqual(context["mr_contact"], "Morgan Reed")

    def test_eastern_date_uses_timezone_calendar_boundary(self):
        self.assertEqual(
            acknowledgement_letter_date(datetime(2026, 7, 27, 3, 59, tzinfo=UTC)),
            "July 26, 2026",
        )
        self.assertEqual(
            acknowledgement_letter_date(datetime(2026, 7, 27, 4, 0, tzinfo=UTC)),
            "July 27, 2026",
        )

    def test_split_amount_and_ad_hoc_mr_contact_render_by_paragraph(self):
        context = self._context()
        with ZipFile(self.template_path) as docx:
            xml = docx.read("word/document.xml").decode("utf-8")
        rendered = DocxTemplateService()._render_document_xml(
            document_xml=xml,
            plan=build_acknowledgement_render_plan(context),
        )
        self.assertIn("July 26, 2026", rendered)
        self.assertIn("Ms. Current Contact", rendered)
        date_position = rendered.find("July 26, 2026")
        recipient_position = rendered.find("Ms. Current Contact")
        between_date_and_recipient = rendered[date_position:recipient_position]
        self.assertEqual(between_date_and_recipient.count("</w:p>"), 2)
        self.assertIn("100 Original Road", rendered)
        self.assertIn("Dear Ms. Contact:", rendered)
        self.assertIn("contribution of $1,250.50 to the Mercy Ridge", rendered)
        self.assertIn("cc: Morgan Reed", rendered)
        self.assertIn("David Denton", rendered)
        self.assertNotIn("Amount_Received", rendered)
        self.assertNotIn("«MR_Contact»", rendered)

    def test_signature_is_embedded_and_pdf_conversion_succeeds(self):
        context = self._context()
        plan = build_acknowledgement_render_plan(
            context, signature_image_path=self.signature_path
        )
        output_docx = self.temp_dir / "acknowledgement.docx"
        DocxTemplateService().render_docx(
            template_path=self.template_path,
            output_path=output_docx,
            plan=plan,
        )
        with ZipFile(output_docx) as docx:
            self.assertTrue(
                any("ellenBreshSig.jpg" in name for name in docx.namelist())
            )
            document_xml = docx.read("word/document.xml").decode("utf-8")
            self.assertGreater(document_xml.rfind("w:drawing"), document_xml.find("Sincerely,"))
            signature_start = document_xml.find("w:drawing")
            signature_end = document_xml.find("Ellen Bresh")
            signature_block = document_xml[signature_start:signature_end]
            self.assertIn('w:before="120"', signature_block)
            self.assertLessEqual(signature_block.count('w:textId="77777777"'), 1)

        pdf_bytes = DocxTemplateService().render_pdf_bytes(
            template_path=self.template_path,
            plan=plan,
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        pdf_path = self.temp_dir / "acknowledgement.pdf"
        pdf_path.write_bytes(pdf_bytes)
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)], capture_output=True, text=True, check=True
        )
        self.assertIn("Pages:           1", result.stdout)


if __name__ == "__main__":
    unittest.main()
