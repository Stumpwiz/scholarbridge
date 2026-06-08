import os

from dotenv import load_dotenv
from flask import Flask
from flask_login import current_user
from sqlalchemy import inspect, text

from app.config import Config
from app.extensions import db, login_manager
from app.models import User


def create_app(config_class: type[Config] = Config) -> Flask:
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_object(config_class)
    app.config["SQLALCHEMY_DATABASE_URI"] = config_class.resolve_database_uri(
        app.instance_path
    )

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.context_processor
    def inject_auth_context():
        def user_can_edit() -> bool:
            return bool(current_user.is_authenticated and current_user.can_edit)

        def user_is_admin() -> bool:
            return bool(current_user.is_authenticated and current_user.is_admin)

        return {
            "user_can_edit": user_can_edit,
            "user_is_admin": user_is_admin,
        }

    with app.app_context():
        _ensure_user_schema_columns()
        _ensure_contact_schema_columns()

    from app.auth import bp as auth_bp
    from app.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app


def _ensure_user_schema_columns() -> None:
    db_uri = str(db.engine.url)
    if not db_uri.startswith("sqlite"):
        return

    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []

    if "role" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'reader'"
        )
    if "avatar_path" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN avatar_path VARCHAR(255)")
    if "password_changed_at" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN password_changed_at DATETIME")

    for statement in statements:
        db.session.execute(text(statement))

    if statements:
        db.session.commit()


def _ensure_contact_schema_columns() -> None:
    db_uri = str(db.engine.url)
    if not db_uri.startswith("sqlite"):
        return

    inspector = inspect(db.engine)
    if "contacts" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("contacts")}
    statements: list[str] = []

    if "middle_initial" not in existing_columns:
        statements.append("ALTER TABLE contacts ADD COLUMN middle_initial VARCHAR(1)")

    for statement in statements:
        db.session.execute(text(statement))

    if statements:
        db.session.commit()
