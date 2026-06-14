import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from app import create_app
from app.config import Config
from app.main.letter_service import generate_solicitation_pdf_bytes
from app.services.docx_template_service import (
    DocxRenderPlan,
    DocxTemplateService,
    ParagraphTextRule,
)
from app.services.letters.types import LetterTemplate
from app.services.formatters import normalize_phone
from app.services.letters.solicitation import build_solicitation_render_plan


class SolicitationLetterServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template_path = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "private"
            / "letter_templates"
            / "solicitation.docx"
        )
        with ZipFile(cls.template_path, "r") as docx:
            cls.document_xml = docx.read("word/document.xml").decode("utf-8")

    def test_normalize_phone_formats_supported_inputs(self):
        self.assertEqual(normalize_phone("4105551212"), "410-555-1212")
        self.assertEqual(normalize_phone("(410) 555-1212"), "410-555-1212")
        self.assertEqual(normalize_phone("410.555.1212"), "410-555-1212")
        self.assertEqual(normalize_phone("410-555-1212"), "410-555-1212")

    def test_docx_engine_replaces_placeholders_and_applies_conditional_removal(self):
        engine = DocxTemplateService()
        xml = (
            "<w:document><w:body>"
            "<w:p><w:r><w:t>DATE_TOKEN</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Hello <<Company>></w:t></w:r></w:p>"
            "<w:p><w:r><w:t><<Address2>></w:t></w:r></w:p>"
            "</w:body></w:document>"
        )
        plan = DocxRenderPlan(
            placeholder_map={"<<Company>>": "Acme Co", "<<Address2>>": ""},
            remove_paragraph_if_empty={"<<Address2>>": ""},
            paragraph_text_rules=(ParagraphTextRule(replacement_text="June 2026", text_equals="DATE_TOKEN"),),
        )

        rendered = engine._render_document_xml(document_xml=xml, plan=plan)
        self.assertIn("June 2026", rendered)
        self.assertIn("Hello Acme Co", rendered)
        self.assertNotIn("<<Address2>>", rendered)

    def test_solicitation_render_plan_applies_current_replacements(self):
        context = {
            "letter_date": "June 2026",
            "salutation": "Ms.",
            "contact_first_name": "Jane",
            "contact_last_name": "Smith",
            "recipient_line": "Ms. Jane Smith",
            "contact_display_name": "Jane Smith",
            "company": "Acme Co",
            "address_1": "100 Main Street",
            "address_2": "",
            "city": "Baltimore",
            "state": "MD",
            "zip_code": "21201",
            "city_state_zip": "Baltimore, MD 21201",
            "amount_requested": "$1,250.00",
            "amount_requested_no_symbol": "1,250.00",
            "solicitor_name": "Alex Adams",
            "solicitor_number": "410-555-1212",
            "solicitor_email": "alex@example.com",
            "mr_contact": "Morgan Reed",
            "mr_contact_phone": "410-555-1214",
            "dear_line": "Ms. Smith",
            "cc_line": "cc: Morgan Reed",
        }
        plan = build_solicitation_render_plan(context)
        engine = DocxTemplateService()
        rendered = engine._render_document_xml(document_xml=self.document_xml, plan=plan)

        self.assertIn("June 2026", rendered)
        self.assertNotIn("Month and Year", rendered)
        self.assertNotIn("«Address_2_»", rendered)
        self.assertIn("Dear Ms. Smith:", rendered)
        self.assertIn("Ms. Jane Smith", rendered)
        self.assertIn("cc: Morgan Reed", rendered)
        self.assertNotIn("«Salutation»", rendered)
        self.assertIn("410-555-1214", rendered)
        self.assertIn("410-555-1212", rendered)
        self.assertNotIn("solicitor", rendered)
        self.assertIn("Acme Co", rendered)
        self.assertIn("$1,250.00", rendered)
        self.assertNotIn("w:highlight", rendered)

    def test_solicitation_render_docx_updates_footer_color(self):
        context = {
            "letter_date": "June 2026",
            "salutation": "Mr.",
            "contact_first_name": "John",
            "contact_last_name": "Jones",
            "recipient_line": "Mr. John Jones",
            "contact_display_name": "John Jones",
            "company": "Acme Co",
            "address_1": "100 Main Street",
            "address_2": "",
            "city": "Baltimore",
            "state": "MD",
            "zip_code": "21201",
            "city_state_zip": "Baltimore, MD 21201",
            "amount_requested": "$300.00",
            "amount_requested_no_symbol": "300.00",
            "solicitor_name": "Alex Adams",
            "solicitor_number": "410-555-1212",
            "solicitor_email": "alex@example.com",
            "mr_contact": "Morgan Reed",
            "mr_contact_phone": "410-555-1214",
            "dear_line": "Mr. Jones",
            "cc_line": "cc: Morgan Reed",
        }
        plan = build_solicitation_render_plan(context)
        engine = DocxTemplateService()

        with tempfile.TemporaryDirectory(prefix="sb_docx_engine_test_") as temp_dir:
            output_docx = Path(temp_dir) / "rendered.docx"
            engine.render_docx(template_path=self.template_path, output_path=output_docx, plan=plan)

            with ZipFile(output_docx, "r") as docx:
                footer_xml = docx.read("word/footer1.xml").decode("utf-8")
                document_xml = docx.read("word/document.xml").decode("utf-8")

        self.assertIn('w:val="990000"', footer_xml)
        self.assertNotIn('w:val="C00000"', footer_xml)
        self.assertIn("June 2026", document_xml)

    def test_letter_template_resolution_is_canonical_only(self):
        with tempfile.TemporaryDirectory(prefix="sb_letter_templates_") as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "app").mkdir()
            (project_root / "docs" / "private").mkdir(parents=True)
            legacy = project_root / "docs" / "private" / "solicitation.docx"
            legacy.write_bytes(b"legacy-template")

            template = LetterTemplate(
                key="solicitation",
                template_filename="solicitation.docx",
                build_render_plan=lambda _: DocxRenderPlan(placeholder_map={}),
            )

            resolved = template.resolve_template_path(app_root_path=str(project_root / "app"))
            expected = project_root / "docs" / "private" / "letter_templates" / "solicitation.docx"

            self.assertEqual(expected, resolved)
            self.assertNotEqual(legacy, resolved)

    def test_generate_solicitation_pdf_bytes_uses_canonical_template_path(self):
        class TestConfig(Config):
            TESTING = True
            SECRET_KEY = "test-secret"

        context = {
            "letter_date": "June 2026",
            "salutation": "Ms.",
            "contact_first_name": "Jane",
            "contact_last_name": "Smith",
            "recipient_line": "Ms. Jane Smith",
            "contact_display_name": "Jane Smith",
            "company": "Acme Co",
            "address_1": "100 Main Street",
            "address_2": "",
            "city": "Baltimore",
            "state": "MD",
            "zip_code": "21201",
            "city_state_zip": "Baltimore, MD 21201",
            "amount_requested": "$1,250.00",
            "amount_requested_no_symbol": "1,250.00",
            "solicitor_name": "Alex Adams",
            "solicitor_number": "410-555-1212",
            "solicitor_email": "alex@example.com",
            "mr_contact": "Morgan Reed",
            "mr_contact_phone": "410-555-1214",
            "dear_line": "Ms. Smith",
            "cc_line": "cc: Morgan Reed",
        }

        app = create_app(TestConfig)
        expected_template_path = (
            Path(app.root_path).parent
            / "docs"
            / "private"
            / "letter_templates"
            / "solicitation.docx"
        )

        with app.app_context():
            with patch(
                "app.main.letter_service.DocxTemplateService.render_pdf_bytes",
                return_value=b"%PDF-canonical",
            ) as render_pdf_bytes:
                result = generate_solicitation_pdf_bytes(context)

        self.assertEqual(b"%PDF-canonical", result)
        self.assertEqual(render_pdf_bytes.call_count, 1)
        self.assertEqual(
            expected_template_path,
            render_pdf_bytes.call_args.kwargs["template_path"],
        )


if __name__ == "__main__":
    unittest.main()
