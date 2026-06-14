from __future__ import annotations

from app.services.letters.solicitation import SOLICITATION_LETTER
from app.services.letters.types import LetterTemplate


LETTER_TYPES: dict[str, LetterTemplate] = {
    SOLICITATION_LETTER.key: SOLICITATION_LETTER,
}


def get_letter_template(letter_type: str) -> LetterTemplate:
    template = LETTER_TYPES.get(letter_type)
    if template is None:
        raise KeyError(f"Unknown letter template type: {letter_type}")
    return template
