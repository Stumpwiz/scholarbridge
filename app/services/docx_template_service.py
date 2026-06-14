from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, UTC
from dataclasses import dataclass, field
from html import escape
from shutil import copy2
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping
from zipfile import ZIP_DEFLATED, ZipFile


class DocxTemplateError(RuntimeError):
    """Raised when DOCX template rendering fails."""


W_PARAGRAPH_RE = re.compile(r"<w:p\b[^>]*>.*?</w:p>", re.DOTALL)
W_TEXT_RE = re.compile(r"<w:t(\s[^>]*)?>(.*?)</w:t>", re.DOTALL)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParagraphTextRule:
    replacement_text: str
    required_tokens: tuple[str, ...] = ()
    starts_with: str | None = None
    text_equals: str | None = None
    first_only: bool = True


@dataclass(frozen=True)
class DocxRenderPlan:
    placeholder_map: Mapping[str, str]
    remove_paragraph_if_empty: Mapping[str, str] = field(default_factory=dict)
    paragraph_text_rules: tuple[ParagraphTextRule, ...] = ()
    part_replacements: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    strip_highlight: bool = False


class DocxTemplateService:
    def render_docx(
        self,
        *,
        template_path: Path,
        output_path: Path,
        plan: DocxRenderPlan,
    ) -> None:
        if not template_path.exists():
            raise DocxTemplateError(f"DOCX template not found: {template_path}")

        with ZipFile(template_path, "r") as source:
            with ZipFile(output_path, "w", ZIP_DEFLATED) as target:
                for info in source.infolist():
                    content = source.read(info.filename)
                    if info.filename == "word/document.xml":
                        content = self._render_document_xml(
                            document_xml=content.decode("utf-8"),
                            plan=plan,
                        ).encode("utf-8")
                    elif info.filename in plan.part_replacements:
                        xml = content.decode("utf-8")
                        for original, replacement in plan.part_replacements[info.filename].items():
                            xml = xml.replace(original, replacement)
                        content = xml.encode("utf-8")
                    target.writestr(info, content)

    def render_pdf_bytes(self, *, template_path: Path, plan: DocxRenderPlan) -> bytes:
        with TemporaryDirectory(prefix="scholarbridge-docx-") as temp_dir:
            temp_path = Path(temp_dir)
            docx_path = temp_path / "rendered.docx"
            self.render_docx(template_path=template_path, output_path=docx_path, plan=plan)
            try:
                self._convert_docx_to_pdf(docx_path=docx_path, output_dir=temp_path)
            except DocxTemplateError:
                preserved_path = self._preserve_failed_docx(docx_path)
                logger.error(
                    "DOCX-to-PDF conversion failed; preserved rendered DOCX at %s",
                    preserved_path,
                )
                raise
            pdf_path = temp_path / "rendered.pdf"
            if not pdf_path.exists():
                raise DocxTemplateError("LibreOffice completed but did not produce a PDF.")
            return pdf_path.read_bytes()

    def _preserve_failed_docx(self, docx_path: Path) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        preserved_path = Path("/tmp") / f"failed-rendered-{timestamp}.docx"
        copy2(docx_path, preserved_path)
        return preserved_path

    def _convert_docx_to_pdf(self, *, docx_path: Path, output_dir: Path) -> None:
        profile_dir = output_dir / "soffice-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        user_installation_uri = profile_dir.resolve().as_uri()
        command = [
            "soffice",
            "--headless",
            f"-env:UserInstallation={user_installation_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ]
        expected_pdf_path = output_dir / f"{docx_path.stem}.pdf"
        result = subprocess.run(
            command,
            cwd=output_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise DocxTemplateError(
                "LibreOffice failed while generating the PDF.\n"
                f"command: {' '.join(command)}\n"
                f"return_code: {result.returncode}\n"
                f"docx_input_path: {docx_path}\n"
                f"expected_pdf_output_path: {expected_pdf_path}\n"
                f"stdout: {result.stdout!r}\n"
                f"stderr: {result.stderr!r}"
            )

    def _render_document_xml(self, *, document_xml: str, plan: DocxRenderPlan) -> str:
        xml = document_xml

        for token, value in plan.remove_paragraph_if_empty.items():
            if not _clean(value):
                xml = W_PARAGRAPH_RE.sub(
                    lambda match: "" if token in match.group(0) else match.group(0),
                    xml,
                )

        for rule in plan.paragraph_text_rules:
            xml = self._replace_paragraph_text_where(
                xml,
                rule=rule,
            )

        for placeholder, replacement in plan.placeholder_map.items():
            xml = xml.replace(placeholder, escape(_clean(replacement)))

        if plan.strip_highlight:
            xml = re.sub(r"<w:highlight\b[^>]*/>", "", xml)

        return xml

    def _replace_paragraph_text_where(self, xml: str, *, rule: ParagraphTextRule) -> str:
        replaced = False

        def replace_paragraph(match):
            nonlocal replaced
            paragraph_xml = match.group(0)
            if rule.first_only and replaced:
                return paragraph_xml
            if not self._matches_paragraph_rule(paragraph_xml, rule):
                return paragraph_xml
            replaced = True
            return _set_paragraph_text(paragraph_xml, rule.replacement_text)

        return W_PARAGRAPH_RE.sub(replace_paragraph, xml)

    def _matches_paragraph_rule(self, paragraph_xml: str, rule: ParagraphTextRule) -> bool:
        text = paragraph_text(paragraph_xml).strip()
        if rule.starts_with is not None and not text.startswith(rule.starts_with):
            return False
        if rule.text_equals is not None and text != rule.text_equals:
            return False
        return all(token in paragraph_xml for token in rule.required_tokens)


def paragraph_text(paragraph_xml: str) -> str:
    return "".join(
        re.sub(r"<[^>]+>", "", match.group(2))
        for match in W_TEXT_RE.finditer(paragraph_xml)
    )


def _set_paragraph_text(paragraph_xml: str, value: str) -> str:
    escaped_value = escape(_clean(value))
    first_match = W_TEXT_RE.search(paragraph_xml)
    if first_match is None:
        return paragraph_xml.replace("</w:p>", f"<w:r><w:t>{escaped_value}</w:t></w:r></w:p>")

    def repl(match):
        nonlocal escaped_value
        attributes = match.group(1) or ""
        if escaped_value is None:
            return f"<w:t{attributes}></w:t>"
        new_value = escaped_value
        escaped_value = None
        return f"<w:t{attributes}>{new_value}</w:t>"

    return W_TEXT_RE.sub(repl, paragraph_xml)


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()
