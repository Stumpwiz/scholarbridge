from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    ROLE_ADMIN = "admin"
    ROLE_EDITOR = "editor"
    ROLE_READER = "reader"
    ROLE_CHOICES = (ROLE_ADMIN, ROLE_EDITOR, ROLE_READER)

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20),
        nullable=False,
        default=ROLE_READER,
        server_default=ROLE_READER,
    )
    person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=True, unique=True)
    avatar_path = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=func.true())
    last_login_at = db.Column(db.DateTime, nullable=True)
    password_changed_at = db.Column(db.DateTime, nullable=True)
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

    @property
    def is_admin(self) -> bool:
        return self.role == self.ROLE_ADMIN

    @property
    def can_edit(self) -> bool:
        return self.role in {self.ROLE_ADMIN, self.ROLE_EDITOR}

    @property
    def display_name(self) -> str:
        if self.person is not None:
            first = self.person.preferred_name or self.person.first_name
            return f"{first} {self.person.last_name}".strip()
        return self.username

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)
        self.password_changed_at = datetime.utcnow()

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
