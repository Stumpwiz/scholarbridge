from datetime import datetime

from sqlalchemy import func

from app.extensions import db


class Partner(db.Model):
    __tablename__ = "partners"

    id = db.Column(db.Integer, primary_key=True)
    partner_name = db.Column(db.String(255), nullable=False, index=True)
    display_name = db.Column(db.String(255), nullable=True)
    partner_type = db.Column(db.String(120), nullable=True)
    address_1 = db.Column(db.String(255), nullable=True)
    address_2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(80), nullable=True)
    postal_code = db.Column(db.String(40), nullable=True)
    email_main = db.Column(db.String(255), nullable=True)
    phone_main = db.Column(db.String(50), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    partner_notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=func.true())
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
    contacts = db.relationship(
        "Contact",
        back_populates="partner",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Partner id={self.id} name={self.partner_name}>"
