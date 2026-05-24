from datetime import datetime

from sqlalchemy import func

from app.extensions import db


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=True)
    last_name = db.Column(db.String(120), nullable=True)
    title = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_primary = db.Column(db.Boolean, nullable=False, default=False, server_default=func.false())
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=func.true())
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
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

    organization = db.relationship("Organization", back_populates="contacts")

    def __repr__(self) -> str:
        return f"<Contact id={self.id} organization_id={self.organization_id}>"
