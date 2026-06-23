"""
Read-only statistics service for ScholarBridge dashboard pages.

All functions return plain dicts so templates can render them without
any model imports.  Every query is a single aggregation pass; no
Python-side loops over large result sets.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.main.solicitation_status import (
    canonicalize_status_counts,
    solicitation_status_query_values,
)
from app.models import Campaign, Partner, Person, Solicitation
from app.models.user import User


# ---------------------------------------------------------------------------
# Partner statistics
# ---------------------------------------------------------------------------

def partner_stats() -> dict:
    """Return summary counts for the Partners page."""
    total = db.session.scalar(select(func.count()).select_from(Partner)) or 0
    active = db.session.scalar(
        select(func.count()).select_from(Partner).where(Partner.is_active.is_(True))
    ) or 0

    # Status counts derived from solicitations (most-recent status per partner)
    # We count distinct partners that have *any* solicitation in each status.
    def _partners_with_status(status: str) -> int:
        return db.session.scalar(
            select(func.count(Solicitation.partner_id.distinct())).where(
                Solicitation.status.in_(solicitation_status_query_values(status))
            )
        ) or 0

    contacted = _partners_with_status("contacted")
    pledged = _partners_with_status("pledged")
    gift_received = _partners_with_status("gift_received")
    declined = _partners_with_status("declined")

    # Partners missing a primary contact (no contact row with is_primary=True)
    from app.models.contact import Contact
    partners_with_primary = db.session.scalar(
        select(func.count(Contact.partner_id.distinct())).where(
            Contact.is_primary.is_(True)
        )
    ) or 0
    missing_primary_contact = total - partners_with_primary

    return {
        "total": total,
        "active": active,
        "inactive": total - active,
        "contacted": contacted,
        "pledged": pledged,
        "gift_received": gift_received,
        "declined": declined,
        "missing_primary_contact": missing_primary_contact,
    }


# ---------------------------------------------------------------------------
# People / User statistics
# ---------------------------------------------------------------------------

def people_stats() -> dict:
    """Return summary counts for the People page."""
    total_people = db.session.scalar(select(func.count()).select_from(Person)) or 0
    active_people = db.session.scalar(
        select(func.count()).select_from(Person).where(Person.is_active.is_(True))
    ) or 0

    # MRPOCs: persons assigned as mrpoc on at least one solicitation
    mrpoc_count = db.session.scalar(
        select(func.count(Solicitation.mrpoc_person_id.distinct())).where(
            Solicitation.mrpoc_person_id.isnot(None)
        )
    ) or 0

    # User role counts
    def _users_with_role(role: str) -> int:
        return db.session.scalar(
            select(func.count()).select_from(User).where(User.role == role)
        ) or 0

    admin_users = _users_with_role(User.ROLE_ADMIN)
    editor_users = _users_with_role(User.ROLE_EDITOR)
    reader_users = _users_with_role(User.ROLE_READER)
    total_users = db.session.scalar(select(func.count()).select_from(User)) or 0

    return {
        "total_people": total_people,
        "active_people": active_people,
        "mrpoc_count": mrpoc_count,
        "total_users": total_users,
        "admin_users": admin_users,
        "editor_users": editor_users,
        "reader_users": reader_users,
    }


# ---------------------------------------------------------------------------
# Campaign statistics
# ---------------------------------------------------------------------------

def campaign_stats() -> dict:
    """Return summary counts for the Campaigns page."""
    total = db.session.scalar(select(func.count()).select_from(Campaign)) or 0
    active = db.session.scalar(
        select(func.count()).select_from(Campaign).where(Campaign.status == "active")
    ) or 0

    total_solicitations = db.session.scalar(
        select(func.count()).select_from(Solicitation)
    ) or 0

    # Not-Ready solicitations: partner not ready, or missing business_volume/amount_requested
    from app.main.status import solicitation_is_ready  # noqa: PLC0415 (avoid circular import)
    all_solicitations = db.session.scalars(
        select(Solicitation).options(
            selectinload(Solicitation.partner).selectinload(Partner.contacts)
        )
    ).all()
    incomplete = sum(1 for s in all_solicitations if not solicitation_is_ready(s))

    total_business_volume = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.business_volume), 0))
    ) or Decimal("0")

    total_requested = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.amount_requested), 0))
    ) or Decimal("0")

    total_received = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.amount_received), 0))
    ) or Decimal("0")

    return {
        "total": total,
        "active": active,
        "total_solicitations": total_solicitations,
        "not_ready_solicitations": incomplete,
        "total_business_volume": total_business_volume,
        "total_requested": total_requested,
        "total_received": total_received,
    }


def campaign_detail_stats(campaign_id: int) -> dict:
    """Return per-campaign statistics for the campaign detail page."""
    sol_count = db.session.scalar(
        select(func.count()).select_from(Solicitation).where(
            Solicitation.campaign_id == campaign_id
        )
    ) or 0

    from app.main.status import solicitation_is_ready  # noqa: PLC0415
    campaign_solicitations = db.session.scalars(
        select(Solicitation)
        .options(selectinload(Solicitation.partner).selectinload(Partner.contacts))
        .where(Solicitation.campaign_id == campaign_id)
    ).all()
    incomplete = sum(1 for s in campaign_solicitations if not solicitation_is_ready(s))

    total_bv = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.business_volume), 0)).where(
            Solicitation.campaign_id == campaign_id
        )
    ) or Decimal("0")

    total_req = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.amount_requested), 0)).where(
            Solicitation.campaign_id == campaign_id
        )
    ) or Decimal("0")

    total_rec = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.amount_received), 0)).where(
            Solicitation.campaign_id == campaign_id
        )
    ) or Decimal("0")

    # Tranche breakdown
    tranche_rows = db.session.execute(
        select(Solicitation.tranche, func.count().label("cnt"))
        .where(Solicitation.campaign_id == campaign_id)
        .group_by(Solicitation.tranche)
        .order_by(Solicitation.tranche)
    ).all()
    tranche_counts = {row.tranche: row.cnt for row in tranche_rows}

    # Status breakdown
    status_rows = db.session.execute(
        select(Solicitation.status, func.count().label("cnt"))
        .where(Solicitation.campaign_id == campaign_id)
        .group_by(Solicitation.status)
    ).all()
    status_counts = canonicalize_status_counts({row.status: row.cnt for row in status_rows})

    return {
        "sol_count": sol_count,
        "not_ready": incomplete,
        "total_bv": total_bv,
        "total_req": total_req,
        "total_rec": total_rec,
        "tranche_counts": tranche_counts,
        "status_counts": status_counts,
    }


# ---------------------------------------------------------------------------
# Solicitation statistics
# ---------------------------------------------------------------------------

def solicitation_stats() -> dict:
    """Return summary counts for the Solicitations page."""
    total = db.session.scalar(select(func.count()).select_from(Solicitation)) or 0

    from app.main.status import solicitation_is_ready  # noqa: PLC0415
    all_solicitations = db.session.scalars(
        select(Solicitation).options(
            selectinload(Solicitation.partner).selectinload(Partner.contacts)
        )
    ).all()
    complete = sum(1 for s in all_solicitations if solicitation_is_ready(s))

    # By status
    status_rows = db.session.execute(
        select(Solicitation.status, func.count().label("cnt"))
        .group_by(Solicitation.status)
    ).all()
    by_status = canonicalize_status_counts({row.status: row.cnt for row in status_rows})

    # By tranche
    tranche_rows = db.session.execute(
        select(Solicitation.tranche, func.count().label("cnt"))
        .group_by(Solicitation.tranche)
        .order_by(Solicitation.tranche)
    ).all()
    by_tranche = {row.tranche: row.cnt for row in tranche_rows}

    total_requested = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.amount_requested), 0))
    ) or Decimal("0")

    total_received = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.amount_received), 0))
    ) or Decimal("0")

    return {
        "total": total,
        "ready": complete,
        "not_ready": total - complete,
        "by_status": by_status,
        "by_tranche": by_tranche,
        "total_requested": total_requested,
        "total_received": total_received,
    }


# ---------------------------------------------------------------------------
# Dashboard (home page) — top-level highlights
# ---------------------------------------------------------------------------

def dashboard_highlights() -> dict:
    """
    Three highest-impact metrics for the home dashboard:
      1. Total donations received (across all campaigns)
      2. Active partners
      3. Solicitation completion rate
    """
    total_received = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.amount_received), 0))
    ) or Decimal("0")

    active_partners = db.session.scalar(
        select(func.count()).select_from(Partner).where(Partner.is_active.is_(True))
    ) or 0

    total_sol = db.session.scalar(select(func.count()).select_from(Solicitation)) or 0
    from app.main.status import solicitation_is_ready  # noqa: PLC0415
    all_solicitations = db.session.scalars(
        select(Solicitation).options(
            selectinload(Solicitation.partner).selectinload(Partner.contacts)
        )
    ).all()
    complete_sol = sum(1 for s in all_solicitations if solicitation_is_ready(s))
    completion_pct = round(complete_sol * 100 / total_sol) if total_sol else None

    gift_received_count = db.session.scalar(
        select(func.count()).select_from(Solicitation).where(
            Solicitation.status.in_(solicitation_status_query_values("gift_received"))
        )
    ) or 0

    total_requested = db.session.scalar(
        select(func.coalesce(func.sum(Solicitation.amount_requested), 0))
    ) or Decimal("0")

    active_campaign_name = None
    active_campaign = db.session.scalar(
        select(Campaign).where(Campaign.status == "active").order_by(Campaign.campaign_year.desc())
    )
    if active_campaign:
        active_campaign_name = active_campaign.campaign_name

    return {
        "total_received": total_received,
        "active_partners": active_partners,
        "total_solicitations": total_sol,
        "completion_pct": completion_pct,
        "gift_received_count": gift_received_count,
        "total_requested": total_requested,
        "active_campaign_name": active_campaign_name,
    }
