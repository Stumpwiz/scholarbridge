from datetime import datetime

from sqlalchemy import CheckConstraint, UniqueConstraint, func

from app.extensions import db


class Solicitation(db.Model):
    __tablename__ = "solicitations"
    __table_args__ = (
        UniqueConstraint("partner_id", "campaign_id", name="uq_solicitation_partner_campaign"),
        CheckConstraint("tranche IN (1, 2, 3)", name="ck_solicitation_tranche"),
        CheckConstraint(
            "status IN ('not_contacted', 'contacted', 'responded', 'donated', 'declined', 'closed')",
            name="ck_solicitation_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False, index=True)
    solicitor_person_id = db.Column(
        db.Integer, db.ForeignKey("persons.id"), nullable=True, index=True
    )
    mrpoc_person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=True, index=True)
    tranche = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    business_volume = db.Column(db.Numeric(12, 2), nullable=True)
    amount_requested = db.Column(db.Numeric(12, 2), nullable=True)
    amount_pledged = db.Column(db.Numeric(12, 2), nullable=False, default=0, server_default="0")
    amount_received = db.Column(db.Numeric(12, 2), nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default="not_contacted", server_default="not_contacted"
    )
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )

    partner = db.relationship("Partner", back_populates="solicitations")
    campaign = db.relationship("Campaign", back_populates="solicitations")
    solicitor = db.relationship(
        "Person",
        back_populates="solicitations_as_solicitor",
        foreign_keys=[solicitor_person_id],
    )
    mrpoc = db.relationship(
        "Person",
        back_populates="solicitations_as_mrpoc",
        foreign_keys=[mrpoc_person_id],
    )

    def __repr__(self) -> str:
        return (
            f"<Solicitation id={self.id} partner_id={self.partner_id} "
            f"campaign_id={self.campaign_id} status={self.status}>"
        )
