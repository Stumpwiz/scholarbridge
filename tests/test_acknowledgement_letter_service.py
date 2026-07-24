import base64
import shutil
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

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


SYNTHETIC_ACKNOWLEDGEMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:r><w:t>«Salutation»«Contact_Last_Name»</w:t></w:r></w:p>
    <w:p><w:r><w:t>«Company»</w:t></w:r></w:p>
    <w:p><w:r><w:t>«Address_1_»</w:t></w:r></w:p>
    <w:p><w:r><w:t>«Address_2_»</w:t></w:r></w:p>
    <w:p><w:r><w:t>«City_», «State_» «Zip»</w:t></w:r></w:p>
    <w:p><w:r><w:t>Dear «Salutation»«Contact_Last_Name»:</w:t></w:r></w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">Thank you for your contribution of </w:t></w:r>
      <w:r><w:t>«Amount_</w:t></w:r><w:r><w:t>Received»</w:t></w:r>
      <w:r><w:t>.</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>Generic acknowledgement body text.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Sincerely,</w:t></w:r></w:p>
    <w:p/><w:p/><w:p/><w:p/>
    <w:p><w:r><w:t>Jordan Example</w:t></w:r></w:p>
    <w:p><w:r><w:t>Committee Chair</w:t></w:r></w:p>
    <w:p><w:r><w:t>cc: «MR_Contact»</w:t></w:r></w:p>
    <w:p><w:r><w:t>David Denton</w:t></w:r></w:p>
    <w:sectPr>
      <w:footerReference w:type="default" r:id="rIdFooter1"/>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"
               w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def create_synthetic_acknowledgement_template(output_path: Path) -> None:
    package_path = Path(__file__).parent / "fixtures" / "minimal_template.docx"
    with ZipFile(package_path) as source:
        parts = {name: source.read(name) for name in source.namelist()}

    parts["word/document.xml"] = SYNTHETIC_ACKNOWLEDGEMENT_XML.encode()
    content_types = parts["[Content_Types].xml"].decode()
    content_types = content_types.replace(
        "</Types>",
        '<Default Extension="png" ContentType="image/png"/></Types>',
    )
    parts["[Content_Types].xml"] = content_types.encode()

    with ZipFile(output_path, "w", ZIP_DEFLATED) as target:
        for name, content in parts.items():
            target.writestr(name, content)


def create_synthetic_signature(output_path: Path) -> None:
    # A deterministic 1x1 PNG is sufficient to exercise OOXML image embedding.
    output_path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
    )


class AcknowledgementLetterServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="sb_ack_service_"))

        class TestConfig(Config):
            TESTING = True
            SECRET_KEY = "test-secret"
            DATABASE_URL = f"sqlite:///{self.temp_dir / 'test.db'}"

        self.app = create_app(TestConfig)
        self.template_path = self.temp_dir / "acknowledgement_template.docx"
        self.signature_path = self.temp_dir / "synthetic_signature.png"
        create_synthetic_acknowledgement_template(self.template_path)
        create_synthetic_signature(self.signature_path)
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

    def _rendered_document_xml(self, context=None):
        context = context or self._context()
        with ZipFile(self.template_path) as docx:
            xml = docx.read("word/document.xml").decode()
        return DocxTemplateService()._render_document_xml(
            document_xml=xml,
            plan=build_acknowledgement_render_plan(context),
        )

    def test_split_run_amount_replacement(self):
        context = self._context()
        rendered = self._rendered_document_xml(context)

        self.assertIn("contribution of $1,250.50 to the Mercy Ridge", rendered)
        self.assertNotIn("Amount_", rendered)
        self.assertNotIn("Received»", rendered)

    def test_mr_contact_paragraph_replacement_preserves_fixed_cc(self):
        rendered = self._rendered_document_xml()

        self.assertIn("cc: Morgan Reed", rendered)
        self.assertIn("David Denton", rendered)
        self.assertNotIn("«MR_Contact»", rendered)

    def test_date_insertion_adds_blank_line_before_recipient(self):
        rendered = self._rendered_document_xml()

        self.assertIn("July 26, 2026", rendered)
        self.assertIn("Ms. Current Contact", rendered)
        date_position = rendered.find("July 26, 2026")
        recipient_position = rendered.find("Ms. Current Contact")
        between_date_and_recipient = rendered[date_position:recipient_position]
        self.assertEqual(between_date_and_recipient.count("</w:p>"), 2)

    def test_empty_address_2_paragraph_is_removed(self):
        context = self._context()
        rendered_with_address_2 = self._rendered_document_xml(context)
        context["address_2"] = ""
        rendered = self._rendered_document_xml(context)

        self.assertNotIn("«Address_2_»", rendered)
        self.assertNotIn("Suite 5", rendered)
        self.assertEqual(
            rendered_with_address_2.count("<w:p>"),
            rendered.count("<w:p>") + 1,
        )
        self.assertIn("100 Original Road", rendered)
        self.assertIn("Dear Ms. Contact:", rendered)

    def test_signature_is_embedded_and_docx_is_created(self):
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
        self.assertTrue(output_docx.is_file())
        with ZipFile(output_docx) as docx:
            self.assertTrue(
                any("synthetic_signature.png" in name for name in docx.namelist())
            )
            document_xml = docx.read("word/document.xml").decode()
            self.assertGreater(document_xml.rfind("w:drawing"), document_xml.find("Sincerely,"))
            drawing_start = document_xml.find("<w:drawing")
            signature_start = document_xml.rfind("<w:p", 0, drawing_start)
            signature_end = document_xml.find("Jordan Example")
            signature_block = document_xml[signature_start:signature_end]
            self.assertIn('w:before="120"', signature_block)
            self.assertLessEqual(signature_block.count('w:textId="77777777"'), 1)

    def test_libreoffice_pdf_conversion_when_available(self):
        if shutil.which("soffice") is None:
            self.skipTest("LibreOffice is not installed")

        context = self._context()
        plan = build_acknowledgement_render_plan(
            context, signature_image_path=self.signature_path
        )
        pdf_bytes = DocxTemplateService().render_pdf_bytes(
            template_path=self.template_path,
            plan=plan,
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
