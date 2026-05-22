from datetime import datetime

from sqlalchemy import func

from app.extensions import db


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(255), nullable=False, index=True)
    display_name = db.Column(db.String(255), nullable=True)
    organization_type = db.Column(db.String(120), nullable=True)
    email_main = db.Column(db.String(255), nullable=True)
    phone_main = db.Column(db.String(50), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    organization_notes = db.Column(db.Text, nullable=True)
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

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.organization_name}>"
