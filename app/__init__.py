import os

from dotenv import load_dotenv
from flask import Flask
from flask_login import current_user

from app.config import Config
from app.db_safety import assert_testing_uses_isolated_database
from app.extensions import db, login_manager, migrate
from app.main.solicitation_status import solicitation_status_label
from app.models import User
from app.services.formatters import eastern_datetime


def create_app(config_class: type[Config] = Config) -> Flask:
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_object(config_class)
    resolved_db_uri = config_class.resolve_database_uri(app.instance_path)
    app.config["SQLALCHEMY_DATABASE_URI"] = resolved_db_uri
    if app.config.get("TESTING"):
        assert_testing_uses_isolated_database(
            str(app.config["SQLALCHEMY_DATABASE_URI"]),
            app.instance_path,
        )

    db.init_app(app)
    migrate.init_app(
        app,
        db,
        render_as_batch=config_class.should_use_batch_migrations(resolved_db_uri),
    )

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"
    app.add_template_filter(eastern_datetime)

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
            "solicitation_status_label": solicitation_status_label,
        }

    from app.auth import bp as auth_bp
    from app.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app
