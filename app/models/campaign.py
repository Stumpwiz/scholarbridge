from datetime import datetime

from sqlalchemy import func

from app.extensions import db


class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(db.Integer, primary_key=True)
    campaign_year = db.Column(db.Integer, nullable=False, unique=True, index=True)
    campaign_name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="planned", server_default="planned")
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
    solicitations = db.relationship(
        "Solicitation",
        back_populates="campaign",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} year={self.campaign_year} status={self.status}>"
