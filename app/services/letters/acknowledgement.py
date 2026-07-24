from __future__ import annotations

from pathlib import Path

from app.services.docx_template_service import (
    DocxRenderPlan,
    ImageInsertion,
    ParagraphInsertion,
    ParagraphTextRule,
)
from app.services.letters.types import LetterTemplate

_SIGNATURE_WIDTH_CM = 2.5
_SIGNATURE_HEIGHT_CM = 2.5 * (131 / 756)
_SIGNATURE_RELATIVE_PATH = Path("docs") / "private" / "img" / "ellenBreshSig.jpg"
_SIGNATURE_SPACE_BEFORE_TWIPS = 120  # 6 pt
_EXTRA_SIGNATURE_BLANK_PARAGRAPHS = 3


def build_acknowledgement_render_plan(
    context: dict, *, signature_image_path: Path | None = None
) -> DocxRenderPlan:
    recipient_marker = "«Salutation»«Contact_Last_Name»"
    return DocxRenderPlan(
        placeholder_map={
            "«Company»": context["company"],
            "«Address_1_»": context["address_1"],
            "«Address_2_»": context["address_2"],
            "«City_»": context["city"],
            "«State_»": context["state"],
            "«Zip»": context["zip_code"],
            "«Contact_Last_Name»": context["contact_last_name"],
            "«Salutation»": "",
        },
        remove_paragraph_if_empty={"«Address_2_»": context["address_2"]},
        paragraph_text_rules=(
            ParagraphTextRule(
                replacement_text=context["recipient_line"],
                required_tokens=("«Salutation»", "«Contact_Last_Name»"),
                text_equals=recipient_marker,
            ),
            ParagraphTextRule(
                replacement_text=context["city_state_zip"],
                text_equals="«City_», «State_» «Zip»",
            ),
            ParagraphTextRule(
                replacement_text=f"Dear {context['dear_line']}:",
                required_tokens=("«Salutation»", "«Contact_Last_Name»"),
                starts_with="Dear ",
            ),
            ParagraphTextRule(
                replacement_text=(
                    f"Thank you for your contribution of {context['amount_received']} "
                    "to the Mercy Ridge Scholarship Fund."
                ),
                starts_with="Thank you for your contribution of",
            ),
            ParagraphTextRule(
                replacement_text=context["cc_line"],
                required_tokens=("MR_Contact",),
                starts_with="cc:",
            ),
        ),
        paragraph_insertions=(
            ParagraphInsertion(before_text=recipient_marker, text=context["letter_date"]),
            ParagraphInsertion(before_text=recipient_marker, text=""),
        ),
        strip_highlight=True,
        image_insertions=(
            (
                ImageInsertion(
                    after_text="Sincerely,",
                    image_path=signature_image_path,
                    width_cm=_SIGNATURE_WIDTH_CM,
                    height_cm=_SIGNATURE_HEIGHT_CM,
                    space_before_twips=_SIGNATURE_SPACE_BEFORE_TWIPS,
                    empty_paragraphs_after_to_remove=_EXTRA_SIGNATURE_BLANK_PARAGRAPHS,
                ),
            )
            if signature_image_path is not None
            else ()
        ),
    )


ACKNOWLEDGEMENT_LETTER = LetterTemplate(
    key="acknowledgement",
    template_filename="acknowledgement.docx",
    build_render_plan=build_acknowledgement_render_plan,
)
