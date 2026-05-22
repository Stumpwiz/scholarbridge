from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import func

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=True, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=func.true())
    last_login_at = db.Column(db.DateTime, nullable=True)
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

    person = db.relationship("Person", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
