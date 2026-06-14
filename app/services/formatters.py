from __future__ import annotations

from datetime import date


def normalize_phone(value: str | None) -> str:
    cleaned = clean(value)
    digits = "".join(character for character in cleaned if character.isdigit())
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return cleaned


def month_year(value: date | None = None) -> str:
    current = value or date.today()
    return current.strftime("%B %Y")


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()
