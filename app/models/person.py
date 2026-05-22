from datetime import datetime

from sqlalchemy import func

from app.extensions import db


class Person(db.Model):
    __tablename__ = "persons"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    preferred_name = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    committee_role = db.Column(db.String(120), nullable=True)
    person_notes = db.Column(db.Text, nullable=True)
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

    user = db.relationship("User", back_populates="person", uselist=False)

    def __repr__(self) -> str:
        return f"<Person id={self.id} name={self.first_name} {self.last_name}>"
