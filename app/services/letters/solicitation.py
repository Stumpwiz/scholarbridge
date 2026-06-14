from __future__ import annotations

from app.services.docx_template_service import DocxRenderPlan, ParagraphTextRule
from app.services.letters.types import LetterTemplate


def build_solicitation_render_plan(context: dict) -> DocxRenderPlan:
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
            "«MR_Contact»": context["mr_contact"],
            "«MR_Contact_Phone_»": context["mr_contact_phone"],
            "$(amount)": context["amount_requested_no_symbol"],
            "(solicitor name)": context["solicitor_name"],
            "solicitor name": context["solicitor_name"],
            "(solicitor phone #)": context["solicitor_number"],
        },
        remove_paragraph_if_empty={
            "«Address_2_»": context["address_2"],
        },
        paragraph_text_rules=(
            ParagraphTextRule(
                replacement_text=context["letter_date"],
                required_tokens=("Month and Year",),
            ),
            ParagraphTextRule(
                replacement_text=f"Dear {context['dear_line']}:",
                required_tokens=("«Salutation»", "«Contact_Last_Name»"),
                starts_with="Dear ",
            ),
            ParagraphTextRule(
                replacement_text=context["recipient_line"],
                required_tokens=("«Salutation»", "«Contact_Last_Name»"),
                text_equals="«Salutation»«Contact_Last_Name»",
            ),
            ParagraphTextRule(
                replacement_text=context["city_state_zip"],
                text_equals="«City_», «State_» «Zip»",
            ),
            ParagraphTextRule(
                replacement_text=(
                    "We would ask that you please consider a donation of "
                    f"${context['amount_requested_no_symbol']}."
                ),
                starts_with="We would ask that you please consider a donation of",
            ),
            ParagraphTextRule(
                replacement_text=(
                    "In a few days, I or a member of the scholarship program team will reach out to you "
                    "to discuss your interest in having your company join with the Mercy Ridge Scholarship "
                    "Program in this important and worthwhile initiative. "
                    "In the interim if you would have any questions prior to my reaching you, "
                    f"please do feel free to contact {context['solicitor_name']} at "
                    f"{context['solicitor_number']}"
                ),
                starts_with="In a few days",
            ),
            ParagraphTextRule(
                replacement_text=context["cc_line"],
                required_tokens=("«MR_Contact»",),
                starts_with="cc:",
            ),
        ),
        part_replacements={
            "word/footer1.xml": {
                'w:val="C00000"': 'w:val="990000"',
            }
        },
        strip_highlight=True,
    )


SOLICITATION_LETTER = LetterTemplate(
    key="solicitation",
    template_filename="solicitation.docx",
    build_render_plan=build_solicitation_render_plan,
)
