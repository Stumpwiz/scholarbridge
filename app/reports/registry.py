from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.main.solicitation_status import (
    SOLICITATION_STATUS_OPTIONS,
    canonical_solicitation_status,
    solicitation_status_label,
)
from app.models import Campaign, Solicitation


@dataclass(frozen=True)
class CampaignByPartnerRow:
    partner_display_name: str
    status: str
    status_date: date | None
    amount_requested: Decimal | None
    amount_pledged: Decimal | None
    amount_received: Decimal | None

    @property
    def status_date_display(self) -> str | None:
        if self.status_date is None:
            return None
        return f"{self.status_date:%b} {self.status_date.day}"


@dataclass(frozen=True)
class CampaignStatusRow:
    key: str
    label: str
    count: int


ContextBuilder = Callable[[Campaign], dict[str, Any]]
FilenameBuilder = Callable[[Campaign], str]


@dataclass(frozen=True)
class ReportDefinition:
    id: str
    label: str
    description: str
    template_name: str
    renderer_type: str
    build_context: ContextBuilder
    build_filename: FilenameBuilder


def _campaign_by_partner_filename(campaign: Campaign) -> str:
    return f"campaign_by_partner_{campaign.campaign_year}.pdf"


def _campaign_by_participation_filename(campaign: Campaign) -> str:
    return f"campaign_by_participation_{campaign.campaign_year}.pdf"


def _campaign_summary_filename(campaign: Campaign) -> str:
    return f"campaign_summary_{campaign.campaign_year}.pdf"


def _campaign_rows(campaign: Campaign) -> list[CampaignByPartnerRow]:
    solicitations = db.session.scalars(
        select(Solicitation)
        .options(
            selectinload(Solicitation.partner),
        )
        .join(Solicitation.partner)
        .where(Solicitation.campaign_id == campaign.id)
        .order_by(Solicitation.id.asc())
    ).all()

    return [
        CampaignByPartnerRow(
            partner_display_name=(
                solicitation.partner.display_name
                or solicitation.partner.partner_name
                if solicitation.partner
                else f"Solicitation #{solicitation.id}"
            ),
            status=solicitation_status_label(solicitation.status),
            status_date=solicitation.status_date,
            amount_requested=solicitation.amount_requested,
            amount_pledged=solicitation.amount_pledged,
            amount_received=solicitation.amount_received,
        )
        for solicitation in solicitations
    ]


def _campaign_context(
    campaign: Campaign,
    rows: list[CampaignByPartnerRow],
) -> dict[str, Any]:
    return {
        "campaign": campaign,
        "rows": rows,
        "total_requested": _total_money(rows, "amount_requested"),
        "total_pledged": _total_money(rows, "amount_pledged"),
        "total_contributed": _total_money(rows, "amount_received"),
    }


def build_campaign_by_partner_context(campaign: Campaign) -> dict[str, Any]:
    rows = sorted(
        _campaign_rows(campaign),
        key=lambda row: row.partner_display_name.casefold(),
    )
    return _campaign_context(campaign, rows)


def build_campaign_by_participation_context(campaign: Campaign) -> dict[str, Any]:
    rows = sorted(
        _campaign_rows(campaign),
        key=lambda row: (
            -(row.amount_received or Decimal("0")),
            row.partner_display_name.casefold(),
        ),
    )
    return _campaign_context(campaign, rows)


def build_campaign_summary_context(campaign: Campaign) -> dict[str, Any]:
    """Build a campaign-only management summary with a complete status lifecycle."""
    solicitations = db.session.scalars(
        select(Solicitation)
        .where(Solicitation.campaign_id == campaign.id)
        .order_by(Solicitation.id.asc())
    ).all()

    status_counts = {status: 0 for status in SOLICITATION_STATUS_OPTIONS}
    for solicitation in solicitations:
        status = canonical_solicitation_status(solicitation.status)
        status_counts[status] = status_counts.get(status, 0) + 1

    status_rows = [
        CampaignStatusRow(
            key=status,
            label=solicitation_status_label(status),
            count=status_counts[status],
        )
        for status in SOLICITATION_STATUS_OPTIONS
    ]

    return {
        "campaign": campaign,
        "total_partners": len({s.partner_id for s in solicitations if s.partner_id is not None}),
        "total_solicitations": len(solicitations),
        "total_solicitors": len(
            {s.solicitor_person_id for s in solicitations if s.solicitor_person_id is not None}
        ),
        "total_tranches": len({s.tranche for s in solicitations if s.tranche is not None}),
        "status_rows": status_rows,
        "status_total": sum(row.count for row in status_rows),
        "total_requested": _total_solicitation_money(solicitations, "amount_requested"),
        "total_pledged": _total_solicitation_money(solicitations, "amount_pledged"),
        "total_contributed": _total_solicitation_money(solicitations, "amount_received"),
    }


def _total_money(rows: list[CampaignByPartnerRow], field_name: str) -> Decimal:
    return sum(
        (getattr(row, field_name) or Decimal("0") for row in rows),
        Decimal("0"),
    )


def _total_solicitation_money(solicitations: list[Solicitation], field_name: str) -> Decimal:
    return sum(
        (getattr(solicitation, field_name) or Decimal("0") for solicitation in solicitations),
        Decimal("0"),
    )


REPORT_REGISTRY: dict[str, ReportDefinition] = {
    "campaign-summary": ReportDefinition(
        id="campaign-summary",
        label="Campaign Summary",
        description="High-level campaign progress, workflow status, and financial totals.",
        template_name="campaign_summary.tex.j2",
        renderer_type="latex_pdf",
        build_context=build_campaign_summary_context,
        build_filename=_campaign_summary_filename,
    ),
    "campaign-by-partner": ReportDefinition(
        id="campaign-by-partner",
        label="Campaign by Partner",
        description="Partner-level campaign status, requested, pledged, and contributed totals.",
        template_name="campaign_by_partner.tex.j2",
        renderer_type="latex_pdf",
        build_context=build_campaign_by_partner_context,
        build_filename=_campaign_by_partner_filename,
    ),
    "campaign-by-participation": ReportDefinition(
        id="campaign-by-participation",
        label="Campaign by Participation",
        description="Campaign results ordered by contributions received.",
        template_name="campaign_by_participation.tex.j2",
        renderer_type="latex_pdf",
        build_context=build_campaign_by_participation_context,
        build_filename=_campaign_by_participation_filename,
    ),
}


def list_reports() -> list[ReportDefinition]:
    return sorted(REPORT_REGISTRY.values(), key=lambda report: report.label)


def get_report(report_id: str) -> ReportDefinition | None:
    return REPORT_REGISTRY.get(report_id)
