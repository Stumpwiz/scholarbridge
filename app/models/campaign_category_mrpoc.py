from datetime import datetime

from sqlalchemy import UniqueConstraint, func

from app.extensions import db


class CampaignCategoryMRPOC(db.Model):
    __tablename__ = "campaign_category_mrpoc"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "partner_category",
            name="uq_campaign_category_mrpoc_campaign_category",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False, index=True)
    partner_category = db.Column(db.String(120), nullable=False, index=True)
    mrpoc_person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False, index=True)
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

    campaign = db.relationship("Campaign", back_populates="category_mrpoc_mappings")
    mrpoc = db.relationship("Person", back_populates="campaign_category_mappings_as_mrpoc")

    def __repr__(self) -> str:
        return (
            f"<CampaignCategoryMRPOC id={self.id} campaign_id={self.campaign_id} "
            f"category={self.partner_category} mrpoc_person_id={self.mrpoc_person_id}>"
        )
