from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


EASTERN_TIME = ZoneInfo("America/New_York")


def normalize_phone(value: str | None) -> str:
    cleaned = clean(value)
    digits = "".join(character for character in cleaned if character.isdigit())
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return cleaned


def month_year(value: date | None = None) -> str:
    current = value or date.today()
    return current.strftime("%B %Y")


def eastern_datetime(value: datetime) -> str:
    """Format a UTC datetime for users in the U.S. Eastern time zone."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(EASTERN_TIME).strftime("%Y-%m-%d %I:%M:%S %p %Z")


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()
