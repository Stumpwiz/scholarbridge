from __future__ import annotations

from collections.abc import Mapping

SOLICITATION_STATUS_OPTIONS = (
    "not_contacted",
    "contacted",
    "pledged",
    "gift_received",
    "declined",
)

_LEGACY_TO_CANONICAL = {
    "responded": "pledged",
    "donated": "gift_received",
    "closed": "declined",
}

_CANONICAL_TO_STORAGE = {
    "pledged": "responded",
    "gift_received": "donated",
}

_CANONICAL_QUERY_VALUES = {
    "not_contacted": ("not_contacted",),
    "contacted": ("contacted",),
    "pledged": ("pledged", "responded"),
    "gift_received": ("gift_received", "donated"),
    "declined": ("declined", "closed"),
}


def canonical_solicitation_status(status: str | None) -> str:
    value = (status or "").strip()
    return _LEGACY_TO_CANONICAL.get(value, value)


def solicitation_status_for_storage(status: str | None) -> str:
    canonical = canonical_solicitation_status(status)
    return _CANONICAL_TO_STORAGE.get(canonical, canonical)


def solicitation_status_query_values(status: str) -> tuple[str, ...]:
    return _CANONICAL_QUERY_VALUES.get(status, (status,))


def solicitation_status_label(status: str | None) -> str:
    canonical = canonical_solicitation_status(status)
    return canonical.replace("_", " ").title()


def canonicalize_status_counts(
    status_counts: Mapping[str, int] | Mapping[str, int | None],
) -> dict[str, int]:
    normalized = {status: 0 for status in SOLICITATION_STATUS_OPTIONS}
    for status, count in status_counts.items():
        canonical = canonical_solicitation_status(status)
        normalized[canonical] = normalized.get(canonical, 0) + int(count or 0)
    return normalized
