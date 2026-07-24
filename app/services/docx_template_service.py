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

_EMU_PER_CM = 914400


class DocxTemplateError(RuntimeError):
    """Raised when DOCX template rendering fails."""


W_PARAGRAPH_RE = re.compile(r"<w:p\b(?![^>]*?/>)[^>]*>.*?</w:p>", re.DOTALL)
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
class ImageInsertion:
    """Insert an inline image after the first paragraph whose text equals `after_text`."""
    after_text: str
    image_path: Path
    width_cm: float
    height_cm: float
    space_before_twips: int = 0
    empty_paragraphs_after_to_remove: int = 0


@dataclass(frozen=True)
class ParagraphInsertion:
    """Insert a text paragraph before the first paragraph matching `before_text`."""
    before_text: str
    text: str


@dataclass(frozen=True)
class DocxRenderPlan:
    placeholder_map: Mapping[str, str]
    remove_paragraph_if_empty: Mapping[str, str] = field(default_factory=dict)
    paragraph_text_rules: tuple[ParagraphTextRule, ...] = ()
    part_replacements: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    strip_highlight: bool = False
    image_insertions: tuple[ImageInsertion, ...] = ()
    paragraph_insertions: tuple[ParagraphInsertion, ...] = ()


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
            existing_rels = source.read("word/_rels/document.xml.rels").decode("utf-8")
            next_rid, image_rid_map = _allocate_image_rids(existing_rels, plan.image_insertions)

            with ZipFile(output_path, "w", ZIP_DEFLATED) as target:
                for info in source.infolist():
                    content = source.read(info.filename)
                    if info.filename == "word/document.xml":
                        content = self._render_document_xml(
                            document_xml=content.decode("utf-8"),
                            plan=plan,
                            image_rid_map=image_rid_map,
                        ).encode("utf-8")
                    elif info.filename == "word/_rels/document.xml.rels" and plan.image_insertions:
                        content = _inject_image_relationships(
                            content.decode("utf-8"), image_rid_map
                        ).encode("utf-8")
                    elif info.filename in plan.part_replacements:
                        xml = content.decode("utf-8")
                        for original, replacement in plan.part_replacements[info.filename].items():
                            xml = xml.replace(original, replacement)
                        content = xml.encode("utf-8")
                    target.writestr(info, content)

                for insertion in plan.image_insertions:
                    media_name = f"word/media/{insertion.image_path.name}"
                    target.writestr(media_name, insertion.image_path.read_bytes())

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

    def _render_document_xml(self, *, document_xml: str, plan: DocxRenderPlan, image_rid_map: dict | None = None) -> str:
        xml = document_xml

        for token, value in plan.remove_paragraph_if_empty.items():
            if not _clean(value):
                xml = W_PARAGRAPH_RE.sub(
                    lambda match: "" if token in match.group(0) else match.group(0),
                    xml,
                )

        for insertion in plan.paragraph_insertions:
            xml = _insert_paragraph_before(xml, insertion)

        for rule in plan.paragraph_text_rules:
            xml = self._replace_paragraph_text_where(
                xml,
                rule=rule,
            )

        for placeholder, replacement in plan.placeholder_map.items():
            xml = xml.replace(placeholder, escape(_clean(replacement)))

        if plan.strip_highlight:
            xml = re.sub(r"<w:highlight\b[^>]*/>", "", xml)

        if image_rid_map:
            for insertion in plan.image_insertions:
                rid = image_rid_map.get(insertion)
                if rid:
                    xml = _insert_image_after_paragraph(xml, insertion, rid)

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


def _insert_paragraph_before(xml: str, insertion: ParagraphInsertion) -> str:
    inserted = False

    def insert(match):
        nonlocal inserted
        paragraph_xml = match.group(0)
        if inserted or paragraph_text(paragraph_xml).strip() != insertion.before_text:
            return paragraph_xml
        inserted = True
        opening_tag = paragraph_xml[: paragraph_xml.find(">") + 1]
        paragraph_properties = re.search(r"<w:pPr\b[^>]*>.*?</w:pPr>", paragraph_xml, re.DOTALL)
        properties_xml = paragraph_properties.group(0) if paragraph_properties else ""
        value = escape(_clean(insertion.text))
        new_paragraph = (
            f"{opening_tag}{properties_xml}<w:r><w:t>{value}</w:t></w:r></w:p>"
        )
        return new_paragraph + paragraph_xml

    return W_PARAGRAPH_RE.sub(insert, xml)


def _allocate_image_rids(
    existing_rels_xml: str, insertions: tuple[ImageInsertion, ...]
) -> tuple[int, dict]:
    """Return (next_rid_int, {ImageInsertion: rId_string}) for each insertion."""
    existing_ids = re.findall(r'Id="rId(\d+)"', existing_rels_xml)
    next_rid = max((int(n) for n in existing_ids), default=0) + 1
    rid_map: dict[ImageInsertion, str] = {}
    for insertion in insertions:
        rid_map[insertion] = f"rId{next_rid}"
        next_rid += 1
    return next_rid, rid_map


def _inject_image_relationships(rels_xml: str, rid_map: dict) -> str:
    """Add image relationship entries before the closing </Relationships> tag."""
    image_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    new_entries = []
    for insertion, rid in rid_map.items():
        target = f"media/{insertion.image_path.name}"
        new_entries.append(
            f'<Relationship Id="{rid}" Type="{image_type}" Target="{target}"/>'
        )
    return rels_xml.replace("</Relationships>", "".join(new_entries) + "</Relationships>")


def _insert_image_after_paragraph(xml: str, insertion: ImageInsertion, rid: str) -> str:
    """Insert an inline-image paragraph immediately after the first paragraph matching after_text."""
    cx = int(insertion.width_cm * _EMU_PER_CM)
    cy = int(insertion.height_cm * _EMU_PER_CM)
    drawing_para = (
        '<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
        ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        ' xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<w:pPr><w:spacing w:before="{insertion.space_before_twips}" w:after="0"/></w:pPr>'
        "<w:r><w:drawing>"
        "<wp:inline distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\">"
        f"<wp:extent cx=\"{cx}\" cy=\"{cy}\"/>"
        "<wp:effectExtent l=\"0\" t=\"0\" r=\"0\" b=\"0\"/>"
        "<wp:docPr id=\"1\" name=\"Signature\"/>"
        "<wp:cNvGraphicFramePr>"
        "<a:graphicFrameLocks xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\""
        " noChangeAspect=\"1\"/>"
        "</wp:cNvGraphicFramePr>"
        "<a:graphic xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">"
        "<a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
        "<pic:pic xmlns:pic=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">"
        "<pic:nvPicPr>"
        "<pic:cNvPr id=\"0\" name=\"Signature\"/>"
        "<pic:cNvPicPr/>"
        "</pic:nvPicPr>"
        "<pic:blipFill>"
        f"<a:blip r:embed=\"{rid}\"/>"
        "<a:stretch><a:fillRect/></a:stretch>"
        "</pic:blipFill>"
        "<pic:spPr>"
        "<a:xfrm><a:off x=\"0\" y=\"0\"/>"
        f"<a:ext cx=\"{cx}\" cy=\"{cy}\"/>"
        "</a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        "</pic:spPr>"
        "</pic:pic>"
        "</a:graphicData>"
        "</a:graphic>"
        "</wp:inline>"
        "</w:drawing></w:r></w:p>"
    )

    inserted = False
    empty_paragraphs_removed = 0

    def maybe_insert(match):
        nonlocal inserted, empty_paragraphs_removed
        para_xml = match.group(0)
        if inserted:
            if (
                empty_paragraphs_removed < insertion.empty_paragraphs_after_to_remove
                and not paragraph_text(para_xml).strip()
            ):
                empty_paragraphs_removed += 1
                return ""
            return para_xml
        text = paragraph_text(para_xml).strip()
        if text == insertion.after_text:
            inserted = True
            return para_xml + drawing_para
        return para_xml

    rendered = W_PARAGRAPH_RE.sub(maybe_insert, xml)
    if inserted and empty_paragraphs_removed < insertion.empty_paragraphs_after_to_remove:
        prefix, separator, suffix = rendered.partition(drawing_para)
        while empty_paragraphs_removed < insertion.empty_paragraphs_after_to_remove:
            suffix, removed = re.subn(r"^\s*<w:p\b[^>]*/>", "", suffix, count=1)
            if not removed:
                break
            empty_paragraphs_removed += 1
        rendered = prefix + separator + suffix
    return rendered
