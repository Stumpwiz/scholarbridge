import os

from dotenv import load_dotenv
from flask import Flask

from app.config import Config
from app.extensions import db, login_manager


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
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(_user_id: str):
        # Phase 1A placeholder. User lookup will be implemented with model/auth work.
        return None

    from app.auth import bp as auth_bp
    from app.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app
